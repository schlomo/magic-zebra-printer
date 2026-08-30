#!/usr/bin/env python3

# Configuration constants
CONTENT_WIDTH_CM = 10.0  # Content width in cm
RIGHT_MARGIN_CM = 0.6    # Right margin in cm
PAPER_WIDTH_CM = CONTENT_WIDTH_CM + RIGHT_MARGIN_CM  # Total paper width

"""
   Copyright 2021-2025 Schlomo Schapiro

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

   See the License for the specific language governing permissions and
   limitations under the License.
"""

import sys, os

# This runs as a macOS drag-and-drop target launched by launchd, which provides
# a minimal PATH that doesn't include Homebrew. Prepend it so `sh` can find
# Homebrew-installed binaries like ImageMagick's `convert`.
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import pypdf, math, sh, tempfile
from pathlib import Path
from sh import lp, lpstat, ErrorReturnCode, CommandNotFound
from fpdf import FPDF

# Where the last-used address-label sender is remembered between runs.
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "magic-zebra-printer"
SENDER_FILE = CONFIG_DIR / "sender"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _osascript_escape(text):
    """Escape a string for embedding in a double-quoted AppleScript literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(msg, title="Printing"):
    print(f"{title}\n{msg}")
    if sys.platform == "darwin":
        script = f'display notification "{_osascript_escape(msg)}" with title "{_osascript_escape(title)}"'
        try:
            sh.osascript("-e", script)
        except (ErrorReturnCode, CommandNotFound):
            pass  # notification is best-effort
    elif sys.platform.startswith("linux"):
        try:
            sh.Command("notify-send")(title, msg)
        except (ErrorReturnCode, CommandNotFound):
            pass  # notification is best-effort


def getPrinter():
    if "MAGIC_ZEBRA_PRINTER" in os.environ:
        return os.environ.get("MAGIC_ZEBRA_PRINTER")
    # Force the C locale: `lpstat -p` output is otherwise localized and the
    # "idle" match below finds nothing in non-English locales. LANGUAGE takes
    # precedence over LC_ALL/LANG for CUPS, so it must be forced too.
    lines = lpstat(
        "-p", _env={**os.environ, "LANG": "C", "LC_ALL": "C", "LANGUAGE": "C"}
    ).split("\n")
    for line in lines:
        if not "idle" in line:
            continue
        printer = line.split(" ")[1]
        if "zebra" in printer.lower():
            return printer
    die("Cannot find any Zebra printer")


def viaConvert(anyFile, printer, shouldprint=True):
    """Convert non-PDF files to PDF and process via viaPYPDF."""
    # `from sh import convert` resolves the command eagerly, so a missing
    # binary must be caught here (ImportError), not via a later call. Only
    # done here, not at module level, since the PDF-only path never needs it.
    try:
        from sh import convert

        convert("-version")
    except (ImportError, ErrorReturnCode, CommandNotFound):
        die(
            "ImageMagick's `convert` not found. Install it with "
            "`brew install imagemagick` (Mac) or `sudo apt install imagemagick` (Linux)."
        )

    base_without_ext = os.path.splitext(anyFile)[0]

    # Create a temporary PDF file
    temp_pdf = f"{base_without_ext}_temp.pdf"

    # Convert to PDF using ImageMagick
    # We don't resize here - let viaPYPDF handle all the sizing
    try:
        convert(
            anyFile,
            "-density", "208",  # High quality conversion
            temp_pdf
        )
    except Exception as e:
        die(f"Failed to convert {anyFile} to PDF: {e}")
    
    try:
        # Process the temporary PDF through the standard PDF pipeline
        # Pass the original filename so viaPYPDF can generate the correct output name
        result = viaPYPDF(temp_pdf, printer, shouldprint, original_filename=anyFile)
        return result
    finally:
        # Clean up temporary PDF
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)


def viaPYPDF(pdfFile, printer, shouldprint=True, original_filename=None, auto_rotate=True):
    """
    Process a PDF file for printing.

    Args:
        pdfFile: The PDF file to process
        printer: The printer to use
        shouldprint: Whether to actually print or just convert
        original_filename: The original filename (if different from pdfFile, e.g., when converting from image)
        auto_rotate: Rotate a landscape page to portrait to maximize print size.
            Disable for content that is already correctly oriented by construction
            (e.g. a rendered address label), where this would instead rescale and
            stretch it.
    """
    
    def getSize(page):
        # Use cropbox instead of mediabox to respect cropping
        box = page.cropbox
        return (box.width, box.height)

    def printDebugInfo(page, stage, width, height, rotation):
        print(f"\n{stage}:")
        print(f"  Dimensions: {width:.1f}×{height:.1f}")
        print(f"  Rotation: {rotation}°")
        print(f"  CropBox: {page.cropbox}")
        print(f"  MediaBox: {page.mediabox}")

    reader = pypdf.PdfReader(pdfFile)
    writer = pypdf.PdfWriter()

    if len(reader.pages) == 0:
        die(f"{pdfFile} has zero pages")

    content_width = CONTENT_WIDTH_CM * 72 / 2.54  # Use constant
    margin_right = RIGHT_MARGIN_CM * 72 / 2.54  # Use constant
    page_width = content_width + margin_right  # Total page width
    print(f"\nTarget content width: {content_width:.1f} points ({content_width/72:.1f} inches)")
    print(f"Right margin: {margin_right:.1f} points ({RIGHT_MARGIN_CM*10:.1f}mm)")
    print(f"Total page width: {page_width:.1f} points ({PAPER_WIDTH_CM*10:.1f}mm)")

    page_infos = []
    for page_num, page in enumerate(reader.pages):
        print(f"\nProcessing page {page_num + 1}:")
        
        # Get initial state
        rotation = page.rotation
        width, height = getSize(page)
        printDebugInfo(page, "Initial state", width, height, rotation)

        # Create a new page with the same size as the cropped area
        new_page = pypdf.PageObject.create_blank_page(
            width=page.cropbox.width,
            height=page.cropbox.height
        )

        # Calculate the transformation to map from media box to crop box
        crop = page.cropbox

        # Create transformation matrix
        transform = pypdf.Transformation()
        transform = transform.translate(-crop.left, -crop.bottom)
        
        # Copy the content with transformation
        new_page.merge_transformed_page(page, transform)

        # Handle rotation
        if rotation == 90:
            print(f"\nHandling 90° rotation:")
            # For 90° rotation, we need to swap dimensions
            width, height = height, width
            # Create a new page with swapped dimensions
            rotated_page = pypdf.PageObject.create_blank_page(
                width=width,
                height=height
            )
            # Create transformation: rotate -90° (270°) and translate to center
            transform = pypdf.Transformation()
            transform = transform.rotate(-90).translate(0, height)
            rotated_page.merge_transformed_page(new_page, transform)
            new_page = rotated_page
            printDebugInfo(new_page, "After rotation", width, height, 0)
        elif rotation == 270 or rotation == -90:
            print(f"\nHandling 270° rotation:")
            # For 270° rotation, we need to swap dimensions
            width, height = height, width
            # Create a new page with swapped dimensions
            rotated_page = pypdf.PageObject.create_blank_page(
                width=width,
                height=height
            )
            # Create transformation: rotate 90° and translate
            transform = pypdf.Transformation()
            transform = transform.rotate(90).translate(width, 0)
            rotated_page.merge_transformed_page(new_page, transform)
            new_page = rotated_page
            printDebugInfo(new_page, "After rotation", width, height, 0)
        elif rotation == 180 or rotation == -180:
            print(f"\nHandling 180° rotation:")
            # For 180° rotation, dimensions stay the same
            # Create a new page with same dimensions
            rotated_page = pypdf.PageObject.create_blank_page(
                width=width,
                height=height
            )
            # Create transformation: rotate 180° and translate
            transform = pypdf.Transformation()
            transform = transform.rotate(180).translate(width, height)
            rotated_page.merge_transformed_page(new_page, transform)
            new_page = rotated_page
            printDebugInfo(new_page, "After rotation", width, height, 0)
        elif rotation != 0:
            print(f"\nHandling {rotation}° rotation:")
            # For other rotations, use the existing rotate method
            new_page.rotate(-rotation)
            width, height = getSize(new_page)
            printDebugInfo(new_page, "After rotation", width, height, 0)

        # Check if we need to rotate landscape to portrait
        if auto_rotate and width > height:
            print(f"\nHandling landscape to portrait rotation:")
            # Swap dimensions
            width, height = height, width
            # Create a new page with swapped dimensions
            rotated_page = pypdf.PageObject.create_blank_page(
                width=width,
                height=height
            )
            # Create transformation: rotate -90° and translate
            transform = pypdf.Transformation()
            transform = transform.rotate(-90).translate(0, height)
            rotated_page.merge_transformed_page(new_page, transform)
            new_page = rotated_page
            printDebugInfo(new_page, "After landscape rotation", width, height, 0)

        # Calculate scaling to fit the content to 100mm width while maintaining aspect ratio
        scale_factor = content_width / width
        content_height = math.ceil(height * scale_factor)
        
        # Page height is same as content height (no top/bottom margins)
        page_height = content_height

        print(f"\nScaling:")
        print(f"  Original: {width:.1f}×{height:.1f}")
        print(f"  Content: {content_width:.1f}×{content_height:.1f}")
        print(f"  Page size: {page_width:.1f}×{page_height:.1f}")
        print(f"  Scale factor: {scale_factor:.1%}")

        # First scale the content to the target size
        new_page.scale_to(content_width, content_height)
        
        # Create a larger page with the right margin
        final_page = pypdf.PageObject.create_blank_page(
            width=page_width,
            height=page_height
        )
        
        # Merge the scaled content onto the larger page (positioned at left edge)
        final_page.merge_page(new_page)
        
        writer.add_page(final_page)

        page_infos.append(
            f"page {page_num + 1}: {width:.1f}×{height:.1f} {rotation}° ⇒ {round(page_width)}x{round(page_height)} (content: {round(content_width)}x{round(content_height)}) {scale_factor:.1%}"
        )

    info = "\n".join(page_infos)

    # Generate output filename based on original filename if provided
    if original_filename:
        # For converted files, use the original filename with its extension
        base_without_ext = os.path.splitext(original_filename)[0]
        original_ext = os.path.splitext(original_filename)[1][1:]  # Extension without dot
        outPdfFile = f"{base_without_ext}_{original_ext}_print.pdf"
        display_name = os.path.basename(original_filename)
    else:
        # For PDF files, use the standard naming
        outPdfFile = os.path.splitext(pdfFile)[0] + "_print.pdf"
        display_name = os.path.basename(pdfFile)
    
    with open(outPdfFile, "wb") as f:
        writer.write(f)

    if shouldprint:
        # Round to integers for CUPS compatibility
        page_width_int = round(page_width)
        page_height_int = round(page_height)
        lp(
            "-d",
            printer,
            "-t",
            display_name,  # Use the display name for the print job
            "-o",
            f"PageSize=Custom.{page_width_int}x{page_height_int}",
            outPdfFile,
        )
        os.remove(outPdfFile)
        return (info, f"Printing on {printer}")
    return (info, f"Converted {display_name} → {outPdfFile}")


def load_sender():
    """Read the remembered sender line, or "" if none was saved yet."""
    try:
        return SENDER_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_sender(sender):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SENDER_FILE.write_text(sender, encoding="utf-8")


def _check_latin1(text):
    """fpdf2's core fonts only support Latin-1; fail clearly on anything else."""
    try:
        text.encode("latin-1")
    except UnicodeEncodeError as e:
        raise ValueError(
            f"Unsupported character {text[e.start:e.end]!r} in {text!r} "
            "- PDF fonts here only support Latin-1 (e.g. German umlauts, no emoji/CJK)"
        ) from e


def _line_height_mm(font_size_pt, leading=1.3):
    return font_size_pt / 72 * 25.4 * leading


def render_address_pdf(sender, recipient, out_path):
    """Render a DIN-5008-style address label at exactly CONTENT_WIDTH_CM wide.

    The page carries no margin of its own - it is sized to the pipeline's
    content width so viaPYPDF's scale factor comes out to 1.0 and the 6mm
    right margin is added there, once, instead of being duplicated here.
    Callers must pass this through viaPYPDF(..., auto_rotate=False): the
    label is already correctly oriented by construction, and viaPYPDF's
    landscape-to-portrait auto-rotate would otherwise rescale and stretch
    these fixed font sizes.
    """
    PADDING_MM = 4
    RULE_GAP_MM = 1.5
    SENDER_PT = 12
    RECIPIENT_PT = 16
    MIN_HEIGHT_MM = 30  # 3cm

    sender = sender.strip()
    recipient_lines = recipient.splitlines()
    if not any(line.strip() for line in recipient_lines):
        raise ValueError("Recipient must not be empty")

    for line in ([sender] if sender else []) + recipient_lines:
        _check_latin1(line)

    width_mm = CONTENT_WIDTH_CM * 10
    printable_width_mm = width_mm - 2 * PADDING_MM

    sender_line_height = _line_height_mm(SENDER_PT)
    recipient_line_height = _line_height_mm(RECIPIENT_PT)
    content_height = (sender_line_height + RULE_GAP_MM if sender else 0) + (
        recipient_line_height * len(recipient_lines)
    )
    height_mm = max(content_height + 2 * PADDING_MM, MIN_HEIGHT_MM)

    pdf = FPDF(unit="mm", format=(width_mm, height_mm))
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.add_page()

    y = PADDING_MM
    if sender:
        pdf.set_font("Helvetica", size=SENDER_PT)
        if pdf.get_string_width(sender) > printable_width_mm:
            raise ValueError(f"Sender line too long to fit on the label: {sender!r}")
        pdf.set_xy(PADDING_MM, y)
        pdf.cell(printable_width_mm, sender_line_height, sender, align="C")
        y += sender_line_height
        pdf.set_line_width(0.2)
        pdf.line(PADDING_MM, y, width_mm - PADDING_MM, y)
        y += RULE_GAP_MM

    pdf.set_font("Helvetica", size=RECIPIENT_PT)
    for line in recipient_lines:
        if pdf.get_string_width(line) > printable_width_mm:
            raise ValueError(f"Recipient line too long to fit on the label: {line!r}")
        pdf.set_xy(PADDING_MM, y)
        pdf.cell(printable_width_mm, recipient_line_height, line, align="L")
        y += recipient_line_height

    pdf.output(str(out_path))


def _show_error_dialog(msg):
    """Best-effort error dialog for the UI flow; die() still reports to stderr either way."""
    try:
        if sys.platform == "darwin":
            script = f'display dialog "{_osascript_escape(msg)}" with title "Error" buttons {{"OK"}} default button "OK"'
            sh.osascript("-e", script)
        elif sys.platform.startswith("linux"):
            sh.Command("zenity")("--error", f"--text={msg}")
    except (ErrorReturnCode, CommandNotFound):
        pass


def _prompt_darwin(sender_default):
    """Two native macOS dialogs: single-line sender, multiline recipient.

    Returns (sender, recipient), or None if the user canceled either dialog.
    """
    try:
        sender_script = (
            f'text returned of (display dialog "Sender:" default answer "{_osascript_escape(sender_default)}")'
        )
        sender = str(sh.osascript("-e", sender_script))
        if sender.endswith("\n"):
            sender = sender[:-1]

        # Newlines in the default answer render the field as multiline.
        recipient_script = 'text returned of (display dialog "Recipient:" default answer "\\n\\n\\n\\n")'
        recipient = str(sh.osascript("-e", recipient_script))
        if recipient.endswith("\n"):
            recipient = recipient[:-1]
    except ErrorReturnCode as e:
        # AppleScript's Cancel error is number -128; the message text itself
        # is localized (not "User canceled" on a non-English system), but the
        # error number in stderr is not.
        if "-128" in str(e.stderr, "utf-8", errors="ignore"):
            return None
        raise

    return sender, recipient


def _prompt_linux(sender_default):
    """zenity --entry for sender, zenity --text-info --editable for recipient."""
    try:
        zenity = sh.Command("zenity")
    except CommandNotFound:
        die("zenity not found. Install it with `sudo apt install zenity`.")

    try:
        sender = str(
            zenity("--entry", "--title=Magic Zebra Printer", "--text=Sender:", f"--entry-text={sender_default}")
        )
        if sender.endswith("\n"):
            sender = sender[:-1]
    except ErrorReturnCode:
        return None  # Cancel

    fd, recipient_file = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        try:
            recipient = str(
                zenity("--text-info", "--editable", "--title=Magic Zebra Printer", f"--filename={recipient_file}")
            )
        except ErrorReturnCode:
            return None  # Cancel
    finally:
        os.remove(recipient_file)

    if recipient.endswith("\n"):
        recipient = recipient[:-1]
    return sender, recipient


def address_label_flow(printer, shouldprint):
    """No-file invocation: prompt for sender/recipient, render, then feed the
    result through the normal PDF pipeline exactly like any other PDF."""
    sender_default = load_sender()

    if sys.platform == "darwin":
        result = _prompt_darwin(sender_default)
    elif sys.platform.startswith("linux"):
        result = _prompt_linux(sender_default)
    else:
        die(f"The address-label UI is not supported on {sys.platform}")

    if result is None:
        sys.exit(0)  # user canceled, not an error
    sender, recipient = result

    # A fixed, friendly filename (rather than mkstemp's random one) so the
    # notification and any kept -noprint output read sensibly.
    tmp_dir = tempfile.mkdtemp(prefix="magic-zebra-printer-")
    tmp_pdf = Path(tmp_dir) / "address-label.pdf"
    try:
        try:
            render_address_pdf(sender, recipient, tmp_pdf)
        except ValueError as e:
            _show_error_dialog(str(e))
            die(str(e))

        save_sender(sender)
        return viaPYPDF(str(tmp_pdf), printer, shouldprint, auto_rotate=False)
    finally:
        if tmp_pdf.exists():
            tmp_pdf.unlink()
        try:
            os.rmdir(tmp_dir)  # only succeeds once nothing is left to keep
        except OSError:
            pass


if __name__ == "__main__":
    # No file argument (or a lone -noprint) opens the address-label UI flow
    # instead of dying; a file argument keeps the existing behavior exactly.
    ui_mode = len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "-noprint")

    if ui_mode:
        shouldprint = len(sys.argv) == 1
    else:
        try:
            anyFile = sys.argv[1]
            if not os.path.exists(anyFile):
                raise Exception(f"{anyFile} doesn't exist")
        except IndexError:
            die("1st arg must be a file")

        except Exception as e:
            die(f"1st arg >{anyFile}< must be a file:\n{e}")

        shouldprint = not (len(sys.argv) > 2 and sys.argv[2] == "-noprint")

    if shouldprint:
        printer = getPrinter()
        print(f"Using printer {printer}")
    else:
        printer = "NONE"
        print("Not printing")

    if ui_mode:
        (msg, title) = address_label_flow(printer, shouldprint)
    else:
        suffix = os.path.splitext(anyFile)[1].lower()
        if suffix == ".pdf":
            (msg, title) = viaPYPDF(anyFile, printer, shouldprint)
        else:
            (msg, title) = viaConvert(anyFile, printer, shouldprint)

    notify(msg, title)

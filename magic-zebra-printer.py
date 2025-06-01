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
import pypdf, math
from sh import lp, lpstat
from notifypy import Notify

try:
    from sh import convert, identify
except:
    import sh

    convert = sh.Command("/opt/homebrew/bin/convert")
    identify = sh.Command("/opt/homebrew/bin/identify")

try:
    from sh import mkbitmap
except:
    import sh

    mkbitmap = sh.Command("/opt/homebrew/bin/mkbitmap")


def notify(msg, title="Printing"):
    notification = Notify(
        default_notification_title=title,
        default_application_name="Magic Zebra Printer",
    )
    notification.message = msg
    notification.send(block=False)
    print(f"{title}\n{msg}")


def getPrinter():
    if "MAGIC_ZEBRA_PRINTER" in os.environ:
        return os.environ.get("MAGIC_ZEBRA_PRINTER")
    lines = lpstat("-p").split("\n")
    for line in lines:
        if not "idle" in line:
            continue
        printer = line.split(" ")[1]
        if "zebra" in printer.lower():
            return printer
    die("Cannot find any Zebra printer")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def viaConvert(anyFile, printer, shouldprint=True):
    printer_density = 208
    # Use constants for dimensions
    content_width_inches = CONTENT_WIDTH_CM / 2.54
    content_width_pts = CONTENT_WIDTH_CM * 72 / 2.54
    page_width_pts = PAPER_WIDTH_CM * 72 / 2.54

    def getSize(file):
        identify_result = identify("-format", "%w %h", file)  # returns width and height
        width, height = identify_result.split(" ")
        return math.ceil(float(width)), math.ceil(float(height))

    width, height = getSize(anyFile)
    convert_to_pdf_args = []
    rotation_info = ""
    if height < width:
        convert_to_pdf_args += ["-rotate", "90"]
        width, height = height, width
        rotation_info = "↺ "

    basename = os.path.basename(anyFile)
    # For non-PDF files, include the original extension in the output name to avoid conflicts
    base_without_ext = os.path.splitext(anyFile)[0]
    original_ext = os.path.splitext(anyFile)[1][1:]  # Extension without dot
    if original_ext.lower() != 'pdf':
        outPdfFile = f"{base_without_ext}_{original_ext}_print.pdf"
    else:
        outPdfFile = f"{base_without_ext}_print.pdf"

    convert_to_pdf_args += [
        "-units",
        "PixelsPerInch",
        "-density",
        printer_density,
        "-resize",
        f"{content_width_inches * printer_density:.0f}",  # Resize content based on constant
        "-extent",
        f"{PAPER_WIDTH_CM * printer_density / 2.54:.0f}x",  # Extend canvas based on constant
        "-gravity",
        "West",  # Align content to the left (west)
        "-background",
        "white",  # White background for the margin
        # "-compress",
        # "LZW",
        "PDF:" + outPdfFile,
    ]

    if "[" in identify(anyFile):
        # multi-image files have [x] for index, convert to PDF
        # TODO: split into single images to optimize via mkbitmap
        convertArgs = [anyFile, "-colorspace", "LinearGray"] + convert_to_pdf_args
        convert(*convertArgs)
    else:
        # single-image files, convert to PNM and optimize with mkbitmap first
        convertArgs = ["-"] + convert_to_pdf_args
        # convert anyFile to PNM, pipe into mkbitmap, pipe into convert to PDF
        convert(
            *convertArgs,
            _in=mkbitmap(
                "-f",
                2,
                "-s",
                2,
                "-t",
                0.48,
                _in=convert(anyFile, "PNM:-", _piped=True),
                _piped=True,
            ),
        )

    print_width, print_height = getSize(outPdfFile)

    if abs(print_width - page_width_pts) > 1:
        print(
            f"Print width error: {print_width} from output PDF file should be {page_width_pts:.0f}"
        )

    info = f"{width}×{height} {rotation_info}⇒ {print_width}x{print_height} (content: {content_width_pts:.0f}pts)"

    if shouldprint:
        lp(
            "-d",
            printer,
            "-t",
            basename,
            f"-o PageSize=Custom.{print_width}x{print_height}",
            outPdfFile,
        )
        os.remove(outPdfFile)
        return (info, f"Printing {basename} on {printer}")
    else:
        return (
            info,
            f"Converted {basename} → {outPdfFile}",
        )


def viaPYPDF(pdfFile, printer, shouldprint=True):

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

    content_width = CONTENT_WIDTH_CM * 72 / 2.54  # Use constant
    margin_right = RIGHT_MARGIN_CM * 72 / 2.54  # Use constant
    page_width = content_width + margin_right  # Total page width
    print(f"\nTarget content width: {content_width:.1f} points ({content_width/72:.1f} inches)")
    print(f"Right margin: {margin_right:.1f} points ({RIGHT_MARGIN_CM*10:.1f}mm)")
    print(f"Total page width: {page_width:.1f} points ({PAPER_WIDTH_CM*10:.1f}mm)")

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
        media = page.mediabox
        
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
        if width > height:
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

        info = f"{width:.1f}×{height:.1f} {rotation}° ⇒ {page_width:.1f}x{page_height:.1f} (content: {content_width:.1f}x{content_height:.1f}) {scale_factor:.1%}"

    outPdfFile = os.path.splitext(pdfFile)[0] + "_print.pdf"
    with open(outPdfFile, "wb") as f:
        writer.write(f)

    if shouldprint:
        lp(
            "-d",
            printer,
            "-o",
            f"PageSize=Custom.{page_width}x{page_height}",
            outPdfFile,
        )
        os.remove(outPdfFile)
        return (info, f"Printing on {printer}")
    return (info, f"Converted {pdfFile} → {outPdfFile}")


if __name__ == "__main__":
    try:
        anyFile = sys.argv[1]
        if not os.path.exists(anyFile):
            raise Exception(f"{anyFile} doesn't exist")
    except IndexError:
        die(f"1st arg >{anyFile}< must be a file")

    except Exception as e:
        die(f"1st arg >{anyFile}< must be a file:\n{e}")

    shouldprint = not (len(sys.argv) > 2 and sys.argv[2] == "-noprint")

    if shouldprint:
        printer = getPrinter()
        print(f"Using printer {printer}")
    else:
        printer = "NONE"
        print("Not printing")

    suffix = os.path.splitext(anyFile)[1].lower()
    if ".pdf" in suffix:
        (msg, title) = viaPYPDF(anyFile, printer, shouldprint)
    else:
        (msg, title) = viaConvert(anyFile, printer, shouldprint)

    notify(msg, title)

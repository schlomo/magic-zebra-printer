#!/usr/bin/env python3

"""
   Copyright 2021 Schlomo Schapiro

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
    printer_width = 4
    print_width_pts = 4 * 72

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
    outPdfFile = os.path.splitext(anyFile)[0] + "_print.pdf"

    convert_to_pdf_args += [
        "-units",
        "PixelsPerInch",
        "-density",
        printer_density,
        "-resize",
        printer_width * printer_density,
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

    if print_width != print_width_pts:
        print(
            f"Print width error: {print_width} from output PDF file should be {print_width_pts}"
        )

    info = f"{width}×{height} {rotation_info}⇒ {print_width}x{print_height}"

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
        box = page.mediabox
        return (box.width, box.height)

    reader = pypdf.PdfReader(pdfFile)
    writer = pypdf.PdfWriter()

    print_width = 4 * 72  # 4 inches * 72 points-per-inch

    for page in reader.pages:
        rotation = page.rotation

        if rotation > 0:
            page.rotate(-rotation).transfer_rotation_to_content()

        width, height = getSize(page)

        if height < width:
            page.rotate(90).transfer_rotation_to_content()
            width, height = height, width

        scale_factor = print_width / width
        print_height = math.ceil(height * scale_factor)

        page.scale_to(print_width, print_height)
        writer.add_page(page)

        info = f"{width:.1f}×{height:.1f} {rotation}° ⇒ {print_width}x{print_height} {scale_factor:.1%}"

    outPdfFile = os.path.splitext(pdfFile)[0] + "_print.pdf"
    with open(outPdfFile, "wb") as f:
        writer.write(f)

    if shouldprint:
        lp(
            "-d",
            printer,
            "-o",
            f"PageSize=Custom.{print_width}x{print_height}",
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

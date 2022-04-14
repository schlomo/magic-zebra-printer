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
import PyPDF2, math
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
    for line in filter(lambda l: "idle" in l, lpstat("-p")):
        printer = line.split(" ")[1]
        if "zebra" in printer.lower():
            return printer
    die("Cannot find any Zebra printer")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def viaConvert(anyFile, printer, shouldprint=True):
    density = 208
    width = 4

    basename = os.path.basename(anyFile)
    outPdfFile = os.path.splitext(anyFile)[0] + "_print.pdf"

    if "[" in identify(anyFile):
        # multi-image files have [x] for index, convert to PDF
        convertArgs = [anyFile, "-colorspace", "LinearGray"]
    else:
        # single-image files, convert to PNM and optimize with mkbitmap first
        convertArgs = [
            mkbitmap(convert(anyFile, "PNM:-"), "-f", 2, "-s", 2, "-t", 0.48),
            "-",
        ]
    convertArgs += [
        "-units",
        "PixelsPerInch",
        "-density",
        density,
        "-resize",
        width * density,
        #"-compress",
        #"LZW",
        "PDF:" + outPdfFile,
    ]
    convert(*convertArgs)
    # /Users/schlomoschapiro/Downloads/2021-07-20 at 16_print.pdf PDF 8x14 8x14+0+0 16-bit sRGB 2597B 0.000u 0:00.000
    identify_result = str(identify("-density", density, outPdfFile))[len(outPdfFile):] # cut off filename from result
    printres = identify_result.split(" ")[2]
    # we use " PDF " to split file name and result
    # → 832x653 or such
    if shouldprint:
        print_width, print_height = printres.split("x")
        print_height = math.ceil(float(print_height))
        lp("-d", printer, "-t", basename, f"-o PageSize=Custom.{print_width}x{print_height}", outPdfFile)
        os.remove(outPdfFile)
        return (f"{basename}: {printres}", f"Printing on {printer}")
    else:
        return (f"{basename} → {outPdfFile}: {printres}", f"Converted")


def viaPYPDF2(pdfFile, printer, shouldprint=True):
    def getSize(page):
        box = page.cropBox
        return (box.getWidth(), box.getHeight())

    def getRotation(page: PyPDF2.pdf.PageObject):
        rotation = page.get("/Rotate")
        if rotation is None:
            rotation = 0
        return rotation

    inPdf = PyPDF2.PdfFileReader(open(pdfFile, "rb"))
    page = inPdf.getPage(0)
    rotation = getRotation(page)

    if rotation == 0:
        width, height = getSize(page)
        (shift_x, shift_y) = page.cropBox.lowerLeft
        shift_x *= -1
        shift_y *= -1

    elif rotation == 270:
        height, width = getSize(page)
        (shift_y, shift_x) = page.cropBox.upperLeft
        shift_y *= -1

    elif rotation == 180:
        width, height = getSize(page)
        (shift_x, shift_y) = page.cropBox.upperRight

    elif rotation == 90:
        height, width = getSize(page)
        (shift_y, shift_x) = page.cropBox.lowerRight
        shift_x *= -1

    else:
        die(f"BAD ROTATION {rotation}")

    print_width = 4 * 72  # 4 inch * 72 points-per-inch
    scale_factor = print_width / width
    print_height = math.ceil(height * scale_factor)

    shift_x *= scale_factor
    shift_y *= scale_factor

    info = f"{width:.1f}×{height:.1f} {rotation}° ⇒ {print_width}x{print_height}\n▶ {shift_x:.1f},{shift_y:.1f} {scale_factor:.1%}"

    outPdf = PyPDF2.PdfFileWriter()
    for inPage in inPdf.pages:
        outPage = outPdf.addBlankPage(print_width, print_height)
        outPage.mergeRotatedScaledTranslatedPage(
            inPage, 360 - rotation, scale_factor, shift_x, shift_y, False
        )
        outPage.compressContentStreams()

    outPdfFile = os.path.splitext(pdfFile)[0] + "_print.pdf"
    with open(outPdfFile, "wb") as f:
        outPdf.write(f)

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

    printer = getPrinter()
    print(f"Using printer {printer}")

    shouldprint = not (len(sys.argv) > 2 and sys.argv[2] == "-noprint")

    suffix = os.path.splitext(anyFile)[1].lower()
    if ".pdf" in suffix:
        (msg, title) = viaPYPDF2(anyFile, printer, shouldprint)
    else:
        (msg, title) = viaConvert(anyFile, printer, shouldprint)

    notify(msg, title)

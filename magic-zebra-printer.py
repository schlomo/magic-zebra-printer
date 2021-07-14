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

import sys, os, PyPDF2, math
from sh import lp, lpstat
from notifypy import Notify


def notify(msg, title="Printing"):
    notification = Notify(
        default_notification_title=title,
        default_application_name="Magic Zebra Printer",
    )
    notification.message = msg
    notification.send(block=False)

def getPrinter():
    if "MAGIC_ZEBRA_PRINTER" in os.environ:
        return os.environ.get("MAGIC_ZEBRA_PRINTER")
    for line in filter(lambda l: "idle" in l, lpstat("-p")):
        printer = line.split(" ")[1]
        if "zebra" in printer.lower():
            return printer
    die("Cannot find any Zebra printer")

def getSize(page):
    box = page.cropBox
    return (box.getWidth(), box.getHeight())

def getRotation(page: PyPDF2.pdf.PageObject):
    rotation = page.get("/Rotate")
    if rotation is None:
        rotation = 0
    return rotation

def die(msg):
    print(msg,file=sys.stderr)
    sys.exit(1)


def processPdfFile(pdfFile):
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
    print(pdfFile)
    print(info)

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


    return outPdfFile, print_width, print_height, info

def printPdf(pdfFile, width, height, printer):
    lp("-d", printer, "-o", f"PageSize=Custom.{width}x{height}", pdfFile)


if __name__ == "__main__":

    try:
        pdfFile = sys.argv[1]
        if not os.path.exists(pdfFile):
            raise Exception(f"{pdfFile} doesn't exist")
    except Exception as e:
        die(f"1st arg must be a PDF file:\n{e}")

    printer = getPrinter()
    print(f"Using printer {printer}")

    filename = os.path.basename(pdfFile)

    try:
        outPdfFile, print_width, print_height, info = processPdfFile(pdfFile)
    except Exception as e:
        die(f"Could not process >{pdfFile}<:\n{e}")

    if len(sys.argv) > 2 and sys.argv[2] == "-noprint":
        notify(info, title=f"Not Printing on {printer}: " + filename)
    else:
        printPdf(outPdfFile, print_width, print_height, printer)
        os.remove(outPdfFile)
        notify(info, title=f"Printing on {printer}: " + filename)

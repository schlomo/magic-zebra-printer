# Magic Zebra Printer

Simple script to automatically determine the paper length for a PDF file (based on the 1st page) and print it on a label printer.

My Zebra label printer has a roll of continuous paper and a cutter so that it can print any page size by simply cutting off the paper at the appropriate length.

My problem is that I use it to print all sorts of shipping labels or other small info pages that have different page sizes. Previously I used to create many different custom page sizes to accomodate different print jobs. With this script everything happens automatically:

* Scale down the page to 4 inch wide
* Determine the page length required for the print job
* Determine the printer (looking for `Zebra*`) to use
* Should work on Mac, Linux & Windows
* Includes PDF Service, Service and Application for MacOS

## Installation

1. Install the prerequisites with `brew install imagemagick potrace`

2. Make sure to have Python 3.6 or later installed.

3. Checkout this Git repo into a directory of your choice, I use `/Users/schlomoschapiro/src/magic-zebra-printer` and you will have to adjust that later.

4. Create a Python 3 Virtual Environment named `venv` via `python3 -m venv venv`.

5. Activate it with `source venv/bin/activate` and install the Python module dependencies with `pip install -r requirements.txt`.

For MacOS to install the integrations:

1. Copy the content of [macos](macos) to your `$HOME` directory.

2. Edit to each of the following files and adjust the path to your Git checkout:

    * `~/Library/PDF Services/Zebra Printer.workflow/Contents/document.wflow`
    * `~/Library/Services/Zebra Printer.workflow/Contents/document.wflow`
    * `~/Applications/Zebra Printer.app/Contents/document.wflow`

   In each file, search for `/Users/schlomoschapiro/src/magic-zebra-printer` and replace it with the path where you checked out the Git repo.

Now you should be able to use the Zebra Printer as a PDF Print Action, as a Service in other apps and Finder and as a standalone application which can serve as a drag-and-drop target.

For Linux and Windows I'm happy to accept your contribution with a suitable integration.

## Usage

Simple open a PDF file with the Zebra Printer application or use the Zebra Printer service or PDF Service with it.

On the command line pass the PDF file to print as the first argument. Optionally pass `-noprint` as second argument to suppress printing. It will leave the intermediate file for you to examine (next to the original file).

To set the printer (instead of using the first printer to contain "zebra" in its name), set the `MAGIC_ZEBRA_PRINTER` environment variable with the name of the desired printer.

## Bugs

Lots. Not much error handling, no tests and I have no clue about MacOS internals and "just got it to work". So I'll be happy to get any feedback.

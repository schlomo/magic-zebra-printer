# Magic Zebra Printer

Simple script to automatically determine the paper length for a PDF file (based on the last page) and print it on a label printer. Also works for image files.

My Zebra label printer has a roll of continuous paper and a cutter so that it can print any page size by simply cutting off the paper at the appropriate length.

My problem is that I use it to print all sorts of shipping labels or other small info pages that have different page sizes. Previously I used to create many different custom page sizes to accomodate different print jobs. With this script everything happens automatically:

* Scale down the page to 4 inch wide
* Determine the page length required for the print job
* Determine the printer (looking for `*zebra*`) to use
* Should work on Mac, Linux & Windows
* Includes PDF Service, Service and Application for MacOS

## Installation

1. Install the prerequisites with `brew install imagemagick potrace` or (Mac) `sudo apt install imagemagick potrace` (Debian/Ubuntu)

2. Make sure to have Python 3.6 or later installed.

3. Checkout this Git repo into a directory of your choice, I use `/Users/schlomo/src/magic-zebra-printer` on MacOS and you will have to adjust that later.

4. Create a Python 3 Virtual Environment named `venv` via `python3 -m venv venv`.

5. Activate it with `source venv/bin/activate` and install the Python module dependencies with `pip install -r requirements.txt`.

### For MacOS to install the integrations

1. Copy the content of [macos](macos) to your `$HOME` directory.

2. Edit to each of the following files and adjust the path to your Git checkout:

    * `~/Library/PDF Services/Zebra Printer.workflow/Contents/document.wflow`
    * `~/Library/Services/Zebra Printer.workflow/Contents/document.wflow`
    * `~/Applications/Zebra Printer.app/Contents/document.wflow`

   In each file, search for `/Users/schlomo/src/magic-zebra-printer` and replace it with the path where you checked out the Git repo.

Now you should be able to use the Zebra Printer as a PDF Print Action, as a Service in other apps and Finder and as a standalone application which can serve as a drag-and-drop target.

### For Linux to install the integrations

1. Edit the path in `linux/magic-zebra-printer.desktop` to match the Git checkout

2. (If you want to print images too) Disable the ImageMagic policy that prevents PDF writing, see <https://stackoverflow.com/questions/52998331/imagemagick-security-policy-pdf-blocking-conversion> for details, typically this should do the trick:

    ```sh
    sudo sed -i '/disable ghostscript format types/,+6d' /etc/ImageMagick-6/policy.xml`
    ```

3. Install the desktop file:

   ```sh
   desktop-file-install --rebuild-mime-info-cache --dir=$HOME/.local/share/applications linux/magic-zebra-printer.desktop
   ```

4. Add the following alias to your shell, e.g. to `$HOME/.bash_aliases`, of course adjusting for the path of the Git checkout:

   ```sh
   function mzp { ( source /home/schlomo/src/magic-zebra-printer/venv/bin/activate ; exec python /home/schlomo/src/magic-zebra-printer/magic-zebra-printer.py "$@" ) }
   ```

Now you can use Magic Zebra Printer to open PDF and image files via the "Open with other application" context menu in the file manager. You can also use it as a command line tool by calling `mzp`

### Windows

For Windows I'm happy to accept your contribution with a suitable integration.

## Usage

Simple open a PDF file with the Magic Zebra Printer application or use the Zebra Printer service or PDF Service with it.

On the command line pass the PDF file to print as the first argument. Optionally pass `-noprint` as second argument to suppress printing. It will leave the intermediate file for you to examine (next to the original file).

To set the printer (instead of using the first printer to contain "zebra" in its name), set the `MAGIC_ZEBRA_PRINTER` environment variable with the name of the desired printer.

## Bugs

* Not much error handling, no tests
* No proper installation, but runs from git checkout
* I have no clue about MacOS internals and "just got it to work". So I'll be happy to get any feedback.
* I couldn't find a way to create a convenient drag-drop target on Linux, feedback & ideas are welcome.

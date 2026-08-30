# Magic Zebra Printer

[![Test](https://github.com/schlomo/magic-zebra-printer/actions/workflows/test.yml/badge.svg)](https://github.com/schlomo/magic-zebra-printer/actions/workflows/test.yml)

*The blog article [My Magic Zebra Printer - Why Software Rules the World
](https://schlomo.schapiro.org/2024/05/my-magic-zebra-printer-why-software.html) has a demo of Magic Zebra Printer in action*

A simple script to automatically determine the paper length for an image or PDF file and print it on a label printer.

My Zebra label printer has a roll of continuous paper 10 cm wide and a cutter so that it can print any page size by simply cutting off the paper at the appropriate length.

My problem is that I use it to print all sorts of shipping labels or other small info pages that have different page sizes. Previously I used to create many different custom page sizes to accomodate different print jobs. With this script everything happens automatically:

* Scale down the content to 10 cm width with a 6 mm right margin (total paper width: 10.6 cm)
* Rotate landscape to portrait to maximize print size
* Determine the page length required for the print job
* Determine the printer (looking for `*zebra*`) to use
* Should work on Mac, Linux & Windows
* Includes PDF Service, Service and Application for MacOS. Application can be put into Dock as drag-n-drop target.
* Also doubles as an address label printer: run it with no file and it prompts for a sender and recipient via native dialogs, then prints a DIN 5008 style address label.

The 6mm right margin is added by default to provide better handling when the label is removed from the printer, preventing content from being too close to the edge.

## Installation

1. Install the prerequisites with `brew install imagemagick` (Mac) or `sudo apt install imagemagick` (Debian/Ubuntu)

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

3. Open the "Privacy & Security" settings and add the `Zebra Printer` Application from your `$HOME/Applications` to the list of applications with *Full Disk Access*. This will enable drag and drop for the application without a security confirmation.

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

Simple open a PDF file with the Magic Zebra Printer application (you can use drag and drop onto the launcher for this) or use the Zebra Printer service or PDF Service with it.

On the command line pass the PDF file to print as the first argument. Optionally pass `-noprint` as second argument to suppress printing. It will leave the intermediate file for you to examine (next to the original file).

To set the printer (instead of using the first printer to contain "zebra" in its name), set the `MAGIC_ZEBRA_PRINTER` environment variable with the name of the desired printer.

### Address labels

Run the script with no file argument (or with `-noprint` as the only argument) to print a DIN 5008 style address label instead:

* A native dialog asks for the **sender** (single line, prefilled with whatever you entered last time) and then the **recipient** (multiline). Cancelling either dialog exits quietly without printing anything.
* The sender is remembered in `$XDG_CONFIG_HOME/magic-zebra-printer/sender` (defaults to `~/.config/magic-zebra-printer/sender`) so you only have to type it once.
* The label shows the sender in 12pt Helvetica, centered, with a thin rule underneath, and the recipient in 16pt Helvetica below it, left-aligned, one line per line typed. Font sizes are fixed - text is never shrunk or wrapped to fit.
* If a line is too long for the label, or contains a character outside Latin-1 (the PDF core fonts don't support emoji or CJK, but German umlauts and ß work fine), you get a clear error dialog and the run stops - nothing is printed. An empty recipient is also rejected; an empty sender is fine (the sender line and rule are simply left out).
* With no `-noprint` it prints the label immediately, same as any other file; with `-noprint` it renders the label, keeps the PDF, and reports its path in the notification instead of printing.
* On Linux this needs `zenity` (`sudo apt install zenity`); on macOS it uses the built-in `osascript`, no extra install needed.

## Bugs

* Not much error handling
* No proper installation, but runs from git checkout
* I have no clue about MacOS internals and "just got it to work". So I'll be happy to get any feedback.
* I couldn't find a way to create a convenient drag-drop target on Linux, feedback & ideas are welcome.

## Testing

The project includes a comprehensive test suite to validate the PDF processing functionality:

```bash
# Test all repository test files
./test_magic_zebra_printer.py

# Test specific external files (won't be added to git)
./test_magic_zebra_printer.py ~/Downloads/my_label.pdf

# Test multiple files
./test_magic_zebra_printer.py file1.pdf file2.pdf file3.pdf
```

### Visual Confirmation Options

```bash
# Open output PDFs automatically after generation
./test_magic_zebra_printer.py --open

# Generate a visual HTML report with thumbnails and open in browser
./test_magic_zebra_printer.py --visual

# Combine options for specific files
./test_magic_zebra_printer.py ~/Downloads/my_label.pdf --visual --open
```

The visual report includes:
- Side-by-side comparison of input and output PDFs
- Thumbnail previews of each page
- Detailed dimension information
- Pass/fail status for each test criterion

### Test Validation

The test suite validates:
- ✓ Output paper width is exactly 10.6cm (300.5 points) including 6mm right margin
- ✓ Content is scaled to 10cm width (283.5 points)
- ✓ Aspect ratio is maintained for the content
- ✓ Orientation is portrait (rotates landscape PDFs)
- ✓ Cropping is respected
- ✓ Various rotation angles (90°, 180°, 270°) are handled correctly

Personal/private PDFs (like shipping labels) can be tested without adding them to the repository.

The suite also covers `render_address_pdf` directly (normal sender+recipient, empty sender, an over-long line, a non-Latin-1 character, German umlauts, and the rendered output going through the full pipeline at exactly 10.6cm paper width). The native dialogs themselves aren't automatable and aren't tested; only the rendering function they call is.

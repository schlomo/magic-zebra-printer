#!/usr/bin/env python3

# Constants
CONTENT_WIDTH_CM = 10.0  # Content width (without margin)
RIGHT_MARGIN_CM = 0.6    # Right margin
TARGET_PAGE_WIDTH_CM = CONTENT_WIDTH_CM + RIGHT_MARGIN_CM  # Page width including margin
TARGET_CONTENT_WIDTH_PTS = CONTENT_WIDTH_CM * 72 / 2.54  # Convert cm to points
TARGET_PAGE_WIDTH_PTS = TARGET_PAGE_WIDTH_CM * 72 / 2.54  # Convert cm to points
TOLERANCE = 0.5  # Allow 0.5 point tolerance for floating point comparisons

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

import os
import sys
import subprocess
import pypdf
import glob
from pathlib import Path
import argparse
import tempfile
import webbrowser
from datetime import datetime
import hashlib

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}{Colors.RESET}\n")

def print_test_result(test_name, passed, message=""):
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{test_name:<40} {status}")
    if message:
        print(f"  {Colors.YELLOW}{message}{Colors.RESET}")

def get_pdf_info(pdf_path, page_num=None):
    """Extract information from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Specific page number (0-indexed), or None for all pages
    
    Returns:
        If page_num is specified: dict with page info
        If page_num is None: list of dicts with info for each page
    """
    try:
        reader = pypdf.PdfReader(pdf_path)
        if len(reader.pages) == 0:
            return None
        
        def get_page_info(page, idx):
            mediabox_width = float(page.mediabox.width)
            mediabox_height = float(page.mediabox.height)
            
            # Check if there's a cropbox different from mediabox
            cropbox_width = float(page.cropbox.width)
            cropbox_height = float(page.cropbox.height)
            
            # Use cropbox dimensions if they differ from mediabox
            if (abs(cropbox_width - mediabox_width) > 1 or 
                abs(cropbox_height - mediabox_height) > 1):
                width = cropbox_width
                height = cropbox_height
                is_cropped = True
            else:
                width = mediabox_width
                height = mediabox_height
                is_cropped = False
            
            # Check for rotation
            rotation = page.rotation if hasattr(page, 'rotation') else 0
            
            return {
                'page_num': idx,
                'width': width,
                'height': height,
                'mediabox_width': mediabox_width,
                'mediabox_height': mediabox_height,
                'rotation': rotation,
                'aspect_ratio': width / height if height > 0 else 0,
                'is_cropped': is_cropped
            }
        
        if page_num is not None:
            # Return info for specific page
            if 0 <= page_num < len(reader.pages):
                return get_page_info(reader.pages[page_num], page_num)
            else:
                return None
        else:
            # Return info for all pages
            return [get_page_info(page, idx) for idx, page in enumerate(reader.pages)]
            
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return None

def create_thumbnail(file_path, output_path, width=200, page_num=0):
    """Create a thumbnail of a PDF page or image file.
    
    Args:
        file_path: Path to the PDF or image file
        output_path: Path for the output PNG file
        width: Target width in pixels
        page_num: Page number to thumbnail (0-indexed, ignored for images)
    """
    try:
        if not file_path.lower().endswith('.pdf'):
            # For images, convert directly to thumbnail
            cmd = [
                'convert',
                file_path,
                '-resize', f'{width}x',
                '-quality', '90',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
            
        # For PDFs, use the existing logic
        reader = pypdf.PdfReader(file_path)
        if len(reader.pages) == 0:
            return False
        
        if page_num >= len(reader.pages):
            return False
            
        page = reader.pages[page_num]
        
        # Check if there's a cropbox different from mediabox
        has_cropbox = (abs(page.cropbox.width - page.mediabox.width) > 1 or 
                      abs(page.cropbox.height - page.mediabox.height) > 1)
        
        if has_cropbox:
            # Create a new PDF with just the cropped area
            writer = pypdf.PdfWriter()
            
            # Create a new page with the cropbox dimensions
            new_page = pypdf.PageObject.create_blank_page(
                width=page.cropbox.width,
                height=page.cropbox.height
            )
            
            # Calculate the transformation to map from media box to crop box
            transform = pypdf.Transformation()
            transform = transform.translate(-page.cropbox.left, -page.cropbox.bottom)
            
            # Copy the content with transformation
            new_page.merge_transformed_page(page, transform)
            writer.add_page(new_page)
            
            # Write to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                writer.write(tmp_file)
                temp_pdf_path = tmp_file.name
                
            # Convert the temporary PDF to PNG
            cmd = [
                'convert',
                '-density', '150',
                f'{temp_pdf_path}[0]',
                '-resize', f'{width}x',
                '-quality', '90',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Clean up temporary file
            os.unlink(temp_pdf_path)
        else:
            # No cropbox, just convert directly
            cmd = [
                'convert',
                '-density', '150',
                f'{file_path}[{page_num}]',  # Specify page number
                '-resize', f'{width}x',
                '-quality', '90',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Colors.YELLOW}Warning: Thumbnail generation failed: {e.stderr.decode()}{Colors.RESET}")
        return False
    except FileNotFoundError:
        print(f"{Colors.YELLOW}Warning: ImageMagick not found, skipping thumbnail generation{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Error creating thumbnail: {e}{Colors.RESET}")
        return False

# Keep the old name for backward compatibility
create_pdf_thumbnail = create_thumbnail

def open_pdf(pdf_path):
    """Open a PDF file using the system's default viewer."""
    try:
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', pdf_path])
        elif sys.platform == 'linux':
            subprocess.run(['xdg-open', pdf_path])
        elif sys.platform == 'win32':
            os.startfile(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")

def run_magic_zebra_printer(input_file):
    """Run the magic-zebra-printer.py script on the input file."""
    try:
        # Run the script with -noprint flag
        result = subprocess.run(
            [sys.executable, './magic-zebra-printer.py', input_file, '-noprint'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False, f"Script failed: {result.stderr}"
        
        # Generate expected output filename based on the new naming scheme
        base_without_ext = os.path.splitext(input_file)[0]
        original_ext = os.path.splitext(input_file)[1][1:]  # Extension without dot
        
        # Match the naming logic in magic-zebra-printer.py
        if original_ext.lower() != 'pdf':
            output_file = f"{base_without_ext}_{original_ext}_print.pdf"
        else:
            output_file = f"{base_without_ext}_print.pdf"
        
        if not os.path.exists(output_file):
            return False, "Output file not created"
        
        return True, output_file
    except Exception as e:
        return False, f"Error running script: {e}"

def validate_output(input_file, output_file):
    """Validate the output PDF meets requirements."""
    input_info = get_file_info(input_file)
    output_info = get_file_info(output_file)
    
    if not input_info or not output_info:
        return False, "Could not read file information"
    
    # Handle both single page (dict) and multi-page (list) returns
    if isinstance(input_info, dict):
        input_info = [input_info]
    if isinstance(output_info, dict):
        output_info = [output_info]
    
    # Check page count matches (images are always single page)
    if len(input_info) != len(output_info):
        return False, [(
            "Page count",
            False,
            f"Input: {len(input_info)} pages, Output: {len(output_info)} pages"
        )]
    
    all_tests = []
    all_passed = True
    
    # Validate each page
    for page_idx, (input_page, output_page) in enumerate(zip(input_info, output_info)):
        page_tests = []
        
        # Test 1: Check width is correct (10cm for both PDFs and images)
        width_diff = abs(output_page['width'] - TARGET_PAGE_WIDTH_PTS)
        width_test = width_diff <= TOLERANCE
        page_tests.append((
            f"Page {page_idx + 1}: Width is {TARGET_PAGE_WIDTH_CM}cm",
            width_test,
            f"Width: {output_page['width']:.1f}pts ({output_page['width']/72*2.54:.2f}cm)"
        ))
        
        # Test 2: Check aspect ratio is maintained
        # The content maintains aspect ratio, but page is wider due to margin
        input_aspect = input_page['aspect_ratio']
        output_aspect = output_page['aspect_ratio']
        
        # If input was landscape and output is portrait, compare inverse aspect ratios
        if input_page['width'] > input_page['height'] and output_page['height'] > output_page['width']:
            input_aspect = 1 / input_aspect
        
        # Calculate expected page aspect ratio considering the margin
        # Content maintains original aspect ratio at 283.5pts width
        # Page is 297.6pts wide with same height as content
        # So page aspect ratio = input aspect ratio * (page width / content width)
        expected_page_aspect = input_aspect * (TARGET_PAGE_WIDTH_PTS / TARGET_CONTENT_WIDTH_PTS)
        
        aspect_ratio_diff = abs(expected_page_aspect - output_aspect)
        aspect_test = aspect_ratio_diff < 0.01  # Allow 1% difference
        
        # Add more context for cropped PDFs or images
        aspect_message = f"Input: {input_aspect:.3f}, Output page: {output_aspect:.3f} (expected: {expected_page_aspect:.3f})"
        if input_page.get('is_cropped'):
            aspect_message += " (input is cropped)"
        elif input_page.get('is_image'):
            aspect_message += " (input is image)"
        
        page_tests.append((
            f"Page {page_idx + 1}: Aspect ratio maintained",
            aspect_test,
            aspect_message
        ))
        
        # Test 3: Check orientation is portrait (height > width) or square
        # For square inputs, the page width/height ratio will be exactly the page/content width ratio
        # due to the right margin. Calculate the maximum allowed ratio dynamically.
        max_ratio = TARGET_PAGE_WIDTH_PTS / TARGET_CONTENT_WIDTH_PTS  # This accounts for margin
        width_height_ratio = output_page['width'] / output_page['height']
        orientation_test = width_height_ratio <= max_ratio * 1.001  # Add tiny tolerance for rounding
        orientation_desc = "portrait" if output_page['height'] > output_page['width'] else "square/landscape"
        page_tests.append((
            f"Page {page_idx + 1}: Orientation is portrait or square",
            orientation_test,
            f"Dimensions: {output_page['width']:.1f}×{output_page['height']:.1f} ({orientation_desc})"
        ))
        
        # Test 4: Check rotation is removed (should be 0)
        rotation_test = output_page['rotation'] == 0
        page_tests.append((
            f"Page {page_idx + 1}: Rotation removed",
            rotation_test,
            f"Output rotation: {output_page['rotation']}° (should be 0°)"
        ))
        
        # Add page tests to all tests
        all_tests.extend(page_tests)
        
        # Check if all tests for this page passed
        page_passed = all(test[1] for test in page_tests)
        if not page_passed:
            all_passed = False
    
    # For single-page PDFs/images, flatten the page prefix for cleaner output
    if len(input_info) == 1:
        all_tests = [(name.replace("Page 1: ", ""), passed, msg) for name, passed, msg in all_tests]
    
    return all_passed, all_tests

def test_file(input_file, args, report_data):
    """Test a single file."""
    print(f"\n{Colors.BOLD}Testing: {input_file}{Colors.RESET}")
    
    # Run the script
    success, output_file = run_magic_zebra_printer(input_file)
    if not success:
        print_test_result("Script execution", False, output_file)
        return False
    
    print_test_result("Script execution", True)
    
    # Create thumbnails immediately after conversion to ensure we capture the right output
    # Use the complete input filename (including extension) to ensure uniqueness
    input_basename = os.path.basename(input_file).replace('.', '_')
    
    # Check if multi-page
    input_info = get_file_info(input_file)
    output_info = get_file_info(output_file)
    
    is_multipage = isinstance(input_info, list) and len(input_info) > 1
    
    # Create directory for thumbnails
    os.makedirs(args.report_dir, exist_ok=True)
    
    input_thumbs = []
    output_thumbs = []
    
    if is_multipage:
        # Create thumbnails for each page
        for page_idx in range(len(input_info)):
            # Input thumbnail
            input_thumb_path = os.path.join(args.report_dir, f"thumb_{input_basename}_input_page_{page_idx}.png")
            create_thumbnail(input_file, input_thumb_path, width=150, page_num=page_idx)
            input_thumbs.append(input_thumb_path)
            
            # Output thumbnail
            output_thumb_path = os.path.join(args.report_dir, f"thumb_{input_basename}_output_page_{page_idx}.png")
            create_thumbnail(output_file, output_thumb_path, width=150, page_num=page_idx)
            output_thumbs.append(output_thumb_path)
    else:
        # Single page - create regular thumbnails
        input_thumb_path = os.path.join(args.report_dir, f"thumb_{input_basename}_input.png")
        create_thumbnail(input_file, input_thumb_path, width=200)
        input_thumbs.append(input_thumb_path)
        
        output_thumb_path = os.path.join(args.report_dir, f"thumb_{input_basename}_output.png")
        create_thumbnail(output_file, output_thumb_path, width=200)
        output_thumbs.append(output_thumb_path)
    
    # Validate output
    passed, tests = validate_output(input_file, output_file)
    
    for test_name, test_passed, message in tests:
        print_test_result(f"  {test_name}", test_passed, message)
    
    # Store data for report including pre-generated thumbnail paths
    report_data.append({
        'input': input_file,
        'output': output_file,
        'passed': passed,
        'tests': tests,
        'input_thumbs': input_thumbs,
        'output_thumbs': output_thumbs,
        'is_multipage': is_multipage
    })
    
    # Open PDFs if requested
    if args.open:
        print(f"Opening {output_file}...")
        open_pdf(output_file)
    
    return passed

def generate_html_report(report_data, report_path):
    """Generate an HTML report with visual comparisons."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Magic Zebra Printer Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .test-case {{ 
            border: 1px solid #ddd; 
            margin: 20px 0; 
            padding: 20px; 
            border-radius: 8px;
            background: #f9f9f9;
        }}
        .test-case.passed {{ border-left: 5px solid #4CAF50; }}
        .test-case.failed {{ border-left: 5px solid #f44336; }}
        .images {{ display: flex; gap: 20px; margin: 20px 0; }}
        .image-container {{ 
            flex: 1; 
            text-align: center;
            border: 1px solid #ddd;
            padding: 10px;
            background: white;
        }}
        .image-container img {{ 
            max-width: 100%; 
            height: auto;
            border: 1px solid #eee;
        }}
        .test-results {{ 
            background: #f0f0f0; 
            padding: 10px; 
            border-radius: 4px;
            margin: 10px 0;
        }}
        .pass {{ color: #4CAF50; font-weight: bold; }}
        .fail {{ color: #f44336; font-weight: bold; }}
        .dimension-info {{
            background: #e3f2fd;
            padding: 8px;
            margin: 5px 0;
            border-radius: 4px;
            font-family: monospace;
        }}
        .page-group {{
            border: 1px solid #e0e0e0;
            margin: 10px 0;
            padding: 10px;
            border-radius: 4px;
            background: #fafafa;
        }}
        .page-group.failed {{
            background: #ffebee;
            border-color: #f44336;
        }}
        .page-thumbnails {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        .page-thumb {{
            text-align: center;
            flex: 0 0 150px;
        }}
        .page-thumb img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .page-label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <h1>Magic Zebra Printer Test Report</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    <p>Target page width: {TARGET_PAGE_WIDTH_CM}cm ({TARGET_PAGE_WIDTH_PTS:.1f} points) - includes {RIGHT_MARGIN_CM}cm right margin</p>
    <p>Target content width: {CONTENT_WIDTH_CM}cm ({TARGET_CONTENT_WIDTH_PTS:.1f} points)</p>
"""
    
    for i, test in enumerate(report_data):
        status_class = 'passed' if test['passed'] else 'failed'
        status_text = '<span class="pass">PASSED</span>' if test['passed'] else '<span class="fail">FAILED</span>'
        
        html += f"""
    <div class="test-case {status_class}">
        <h2>{os.path.basename(test['input'])} - {status_text}</h2>
        
        <div class="test-results">
"""
        
        # Group tests by page
        page_tests = {}
        for test_name, test_passed, message in test['tests']:
            # Extract page number from test name if present
            if test_name.startswith("Page "):
                try:
                    page_num = int(test_name.split(":")[0].replace("Page ", ""))
                    if page_num not in page_tests:
                        page_tests[page_num] = []
                    page_tests[page_num].append((test_name, test_passed, message))
                except:
                    # Single page or no page number
                    if "single" not in page_tests:
                        page_tests["single"] = []
                    page_tests["single"].append((test_name, test_passed, message))
            else:
                # Single page tests
                if "single" not in page_tests:
                    page_tests["single"] = []
                page_tests["single"].append((test_name, test_passed, message))
        
        # Display tests grouped by page
        if "single" in page_tests:
            # Single page PDF
            for test_name, test_passed, message in page_tests["single"]:
                result = '<span class="pass">✓</span>' if test_passed else '<span class="fail">✗</span>'
                html += f"            <div>{result} {test_name}: {message}</div>\n"
        else:
            # Multi-page PDF - show by page
            for page_num in sorted(page_tests.keys()):
                page_all_passed = all(test[1] for test in page_tests[page_num])
                page_class = "" if page_all_passed else "failed"
                html += f'        <div class="page-group {page_class}">\n'
                html += f'            <strong>Page {page_num}</strong>\n'
                for test_name, test_passed, message in page_tests[page_num]:
                    result = '<span class="pass">✓</span>' if test_passed else '<span class="fail">✗</span>'
                    # Remove page prefix for cleaner display
                    clean_name = test_name.split(": ", 1)[1] if ": " in test_name else test_name
                    html += f"            <div>{result} {clean_name}: {message}</div>\n"
                html += '        </div>\n'
        
        html += """        </div>
        
        <div class="images">
            <div class="image-container">
                <h3>Input</h3>
"""
        
        # Use pre-generated thumbnails
        if 'input_thumbs' in test and len(test['input_thumbs']) > 0:
            if test.get('is_multipage', False):
                # Multi-page - show thumbnails in a grid
                html += '                <div class="page-thumbnails">\n'
                for idx, thumb_path in enumerate(test['input_thumbs']):
                    if os.path.exists(thumb_path):
                        thumb_filename = os.path.basename(thumb_path)
                        html += f'''                    <div class="page-thumb">
                        <img src="{thumb_filename}" alt="Page {idx + 1}">
                        <div class="page-label">Page {idx + 1}</div>
                    </div>
'''
                html += '                </div>\n'
            else:
                # Single page - show single thumbnail
                if os.path.exists(test['input_thumbs'][0]):
                    thumb_filename = os.path.basename(test['input_thumbs'][0])
                    html += f'                <img src="{thumb_filename}" alt="Input">\n'
                else:
                    html += '                <p>Thumbnail not available</p>\n'
        else:
            html += '                <p>Thumbnail not available</p>\n'
            
        # Show dimension info for first page
        input_info = get_file_info(test['input'], page_num=0)
        if input_info:
            if input_info.get('is_image'):
                html += f"""                <div class="dimension-info">
                    <strong>Image file</strong><br>
                    Dimensions: {input_info['width_px']} × {input_info['height_px']} pixels<br>
                    Aspect ratio: {input_info['aspect_ratio']:.3f}
                </div>
"""
            elif input_info['is_cropped']:
                html += f"""                <div class="dimension-info">
                    <strong>Crop Box:</strong> {input_info['width']:.1f} × {input_info['height']:.1f} pts<br>
                    ({input_info['width']/72*2.54:.1f} × {input_info['height']/72*2.54:.1f} cm)<br>
                    <strong>Media Box:</strong> {input_info['mediabox_width']:.1f} × {input_info['mediabox_height']:.1f} pts<br>
                    Rotation: {input_info['rotation']}°
                </div>
"""
            else:
                html += f"""                <div class="dimension-info">
                    {input_info['width']:.1f} × {input_info['height']:.1f} pts<br>
                    ({input_info['width']/72*2.54:.1f} × {input_info['height']/72*2.54:.1f} cm)<br>
                    Rotation: {input_info['rotation']}°
                </div>
"""
            
            # Show page count if multi-page
            if test.get('is_multipage', False):
                num_pages = len(test['input_thumbs'])
                html += f"""                <div class="dimension-info" style="margin-top: 5px;">
                    <strong>Multi-page PDF:</strong> {num_pages} pages
                </div>
"""
        
        html += """            </div>
            <div class="image-container">
                <h3>Output</h3>
"""
        
        # Use pre-generated thumbnails
        if 'output_thumbs' in test and len(test['output_thumbs']) > 0:
            if test.get('is_multipage', False):
                # Multi-page - show thumbnails in a grid
                html += '                <div class="page-thumbnails">\n'
                for idx, thumb_path in enumerate(test['output_thumbs']):
                    if os.path.exists(thumb_path):
                        thumb_filename = os.path.basename(thumb_path)
                        html += f'''                    <div class="page-thumb">
                        <img src="{thumb_filename}" alt="Page {idx + 1}">
                        <div class="page-label">Page {idx + 1}</div>
                    </div>
'''
                html += '                </div>\n'
            else:
                # Single page - show single thumbnail
                if os.path.exists(test['output_thumbs'][0]):
                    thumb_filename = os.path.basename(test['output_thumbs'][0])
                    html += f'                <img src="{thumb_filename}" alt="Output">\n'
                else:
                    html += '                <p>Thumbnail not available</p>\n'
        else:
            html += '                <p>Thumbnail not available</p>\n'
            
        # Show dimension info for first page
        output_info = get_file_info(test['output'], page_num=0)
        if output_info:
            html += f"""                <div class="dimension-info">
                    {output_info['width']:.1f} × {output_info['height']:.1f} pts<br>
                    ({output_info['width']/72*2.54:.1f} × {output_info['height']/72*2.54:.1f} cm)<br>
                    Rotation: {output_info['rotation']}°
                </div>
"""
            
            # Show page count if multi-page
            if test.get('is_multipage', False):
                num_pages = len(test['output_thumbs'])
                html += f"""                <div class="dimension-info" style="margin-top: 5px;">
                    <strong>Multi-page PDF:</strong> {num_pages} pages
                </div>
"""
        
        html += """            </div>
        </div>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    with open(report_path, 'w') as f:
        f.write(html)
    
    print(f"\n{Colors.GREEN}Visual report generated: {report_path}{Colors.RESET}")
    return report_path

def get_image_info(image_path):
    """Extract information from an image file."""
    try:
        # Use ImageMagick's identify to get image info
        result = subprocess.run([
            'identify',
            '-format',
            '%w %h %[orientation]',
            image_path
        ], capture_output=True, text=True, check=True)
        
        parts = result.stdout.strip().split()
        width_px = int(parts[0])
        height_px = int(parts[1])
        orientation = parts[2] if len(parts) > 2 else "Undefined"
        
        # For images, we only care about pixel dimensions and aspect ratio
        # Points are only meaningful after conversion to PDF
        return {
            'width': width_px,  # For consistency with PDF interface
            'height': height_px,
            'width_px': width_px,
            'height_px': height_px,
            'rotation': 0,  # Images don't have PDF rotation metadata
            'aspect_ratio': width_px / height_px if height_px > 0 else 0,
            'is_cropped': False,
            'orientation': orientation,
            'is_image': True
        }
    except subprocess.CalledProcessError as e:
        print(f"Error reading image {image_path}: {e.stderr}")
        return None
    except Exception as e:
        print(f"Error reading image {image_path}: {e}")
        return None

def get_file_info(file_path, page_num=None):
    """Get info for either PDF or image files."""
    if file_path.lower().endswith('.pdf'):
        return get_pdf_info(file_path, page_num)
    else:
        # For images, ignore page_num as they're single page
        return get_image_info(file_path)

def main():
    parser = argparse.ArgumentParser(description='Test Magic Zebra Printer')
    parser.add_argument('files', nargs='*', help='PDF files to test (if not specified, tests all repository test files)')
    parser.add_argument('--open', '-o', action='store_true', help='Open output PDFs after generation')
    parser.add_argument('--visual', '-v', action='store_true', help='Generate visual HTML report')
    parser.add_argument('--report-dir', '-r', default='test_reports', help='Directory for test reports (default: test_reports)')
    
    args = parser.parse_args()
    
    print_header("Magic Zebra Printer Test Suite")
    
    # Find all test PDFs
    test_files = []
    
    # Check if specific files were passed as arguments
    if args.files:
        # Test specific files passed as arguments
        test_files = args.files
        print(f"Testing specific files from command line:")
    else:
        # Direct test files - only files starting with 'test'
        import pathlib
        test_path = pathlib.Path('test')
        
        # Find all files starting with 'test' (excluding _print.pdf files)
        for file_path in test_path.glob('test*.*'):
            if (file_path.is_file() 
                and not file_path.name.endswith('_print.pdf')
                and file_path.name != 'test_magic_zebra_printer.py'):
                # Check if it's a supported file type
                ext = file_path.suffix.lower()
                if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg']:
                    test_files.append(str(file_path))
        
        print(f"Found {len(test_files)} test files in repository:")
    
    if not test_files:
        print(f"{Colors.RED}No test files found!{Colors.RESET}")
        print("\nUsage:")
        print("  ./test_magic_zebra_printer.py              # Test all repository test files")
        print("  ./test_magic_zebra_printer.py file1.pdf    # Test specific file(s)")
        print("\nOptions:")
        print("  --open, -o     Open output PDFs after generation")
        print("  --visual, -v   Generate visual HTML report")
        return 1
    
    for f in test_files:
        print(f"  • {f}")
    
    # Run tests
    passed_count = 0
    failed_count = 0
    report_data = []
    
    for file_path in sorted(test_files):
        if test_file(file_path, args, report_data):
            passed_count += 1
        else:
            failed_count += 1
    
    # Generate visual report if requested
    if args.visual:
        os.makedirs(args.report_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(args.report_dir, f'test_report_{timestamp}.html')
        report_path = generate_html_report(report_data, report_path)
        
        # Open report in browser
        webbrowser.open(f'file://{os.path.abspath(report_path)}')
    
    # Summary
    print_header("Test Summary")
    total_tests = passed_count + failed_count
    print(f"Total tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_count}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed_count}{Colors.RESET}")
    
    if failed_count == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! 🎉{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed.{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
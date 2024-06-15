import os                                                       # For File Operations
import re                                                       # For Regex
from pytesseract import image_to_string                         # For OCR
from PIL import Image                                           # For Image Processing
from tqdm import tqdm                                           # For Progress Bar
from concurrent.futures import ThreadPoolExecutor, as_completed # For Parallel Processing
import unicodedata                                              # For Unicode Normalization

# VARIABLES / PROPERTIES
VAULT_PATH = '/Users/paul/Arukas-Pilv/📝 Märkmed/Pauli Obsidiaan/'
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif')
ATTACHMENT_FOLDER = '📎 manused'
OVERWRITE_OCR = False
OCR_LANGUAGES = 'eng+est'



def list_markdown_files(path: str) -> list[str]:
    """
    List all Markdown files in a given directory and its subdirectories.

    This function traverses the directory specified by `path`, including all its subdirectories,
    and collects the paths of all files that have a '.md' extension, indicating Markdown files.

    Parameters:
    - path (str): The root directory path from which to start searching for Markdown files.

    Returns:
    - list: A list of strings, where each string is the full path to a Markdown file found
      within the specified directory or its subdirectories.
    """
    markdown_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(os.path.join(root, file))
    return markdown_files



def extract_image_links(md_file: str, overwrite: bool) -> list[str]:
    """
    Extract image links from a Markdown file, specifically formatted for Obsidian's wiki link syntax.

    This function opens and reads the content of a Markdown file. It then searches for image links
    that are formatted using Obsidian's wiki link syntax (e.g., `![[image.jpg]]`). The search is
    case-insensitive and supports various image file extensions. If the Markdown file contains the
    marker "OCR:", indicating that an OCR scan has already been processed for this file, and the
    `overwrite` parameter is False, the function will return an empty list to avoid overwriting
    existing OCR data.

    Parameters:
    - md_file (str): The path to the Markdown file from which to extract image links.
    - overwrite (bool): A flag indicating whether to overwrite existing OCR data. If False and the
      file contains an "OCR:" marker, no image links will be extracted.

    Returns:
    - list[str]: A list of strings, each representing the path of an image file found within the
      Markdown file. The paths are extracted based on Obsidian's wiki link syntax for images.

    Note:
    - The function assumes that `IMAGE_EXTENSIONS` is a global variable containing a list of
      image file extensions to look for within the Markdown content.
    - The function is designed to work with Obsidian's specific wiki link syntax for embedding
      images and may not correctly identify image links formatted differently.
    """
    image_links = []
    with open(md_file, 'r') as file:
        content = file.read()
        if not overwrite and "OCR:" in content:
            return []
        # Adjust the regex pattern to work with extensions that already include the dot
        extensions_pattern = r"|".join(IMAGE_EXTENSIONS).replace(".", r"\.")
        # Adjusted pattern to correctly match individual Obsidian-wiki image links
        pattern = r'!\[\[([^]]+?(?:' + extensions_pattern + r'))\]\]'
        image_links += re.findall(pattern, content, re.IGNORECASE)
    return image_links



def modify_image_path(image_path):
    """
    Modifies the image path to remove the directory and its contents that match '.resources'.

    This function splits the path by the directory separator, removes any segment (and its contents)
    that ends with '.resources', and then reconstructs the path without that segment.

    Parameters:
    - image_path (str): The original file path of the image.

    Returns:
    - str: The modified file path with the '.resources' directory and its contents removed.
    """
    path_parts = image_path.split(os.sep)
    modified_parts = [part for part in path_parts if '.resources' not in part]
    modified_path = os.sep.join(modified_parts)
    return modified_path



def perform_ocr(image_path: str) -> str:
    """
    Perform OCR (Optical Character Recognition) on an image file.

    This function uses the `image_to_string` method from the Tesseract OCR engine to extract text
    from an image specified by `image_path`. The OCR process is configured to recognize languages
    specified in the global `OCR_LANGUAGES` variable. After extracting the text, the function
    performs a series of string replacements to clean up the OCR result: it strips leading and
    trailing spaces, replaces newline characters and carriage returns with a space, replaces tabs
    with a space, collapses multiple spaces into a single space, replaces double quotes with single
    quotes, and escapes backslashes.

    Parameters:
    - image_path (str): The file path of the image to be processed with OCR.

    Returns:
    - str: The cleaned OCR-extracted text from the image. If an error occurs during the OCR
      process, the function prints an error message and returns None.

    Note:
    - The OCR process is dependent on the Tesseract OCR engine, which must be correctly installed
      and configured in the environment where this function is executed.
    - The `OCR_LANGUAGES` variable should contain the languages to be recognized by the OCR,
      formatted as a string compatible with Tesseract's language options.
    """
    try:
        ocr_text = image_to_string(Image.open(image_path), lang=OCR_LANGUAGES)
        return ocr_text.strip().replace('\n', ' ').replace('\r', '').replace('\t', ' ').replace('  ', ' ').replace(r'"', r"'").replace('\\', '\\\\')
    except Exception as e:
        if "No such file or directory" in str(e) and ".resources" in image_path:
            return perform_ocr(modify_image_path(image_path))
        else:
            print(f"Error processing {image_path}: {e}")
            return None



def update_markdown_file(md_file: str, ocr_text: str) -> None:
    """
    Update a Markdown file with OCR text as a property in its YAML front matter.

    This function reads the content of a specified Markdown file and checks for the presence of
    YAML front matter at the beginning of the file. If YAML front matter exists and already contains
    an "OCR:" property, the function can overwrite it. If the "OCR:" property does
    not exist, it is added with `ocr_text` as its value. If the file does not have YAML front matter,
    the function prepends it with an "OCR:" property containing `ocr_text`.

    The updated content, including the modified or added YAML front matter, is then written back to
    the file.

    Parameters:
    - md_file (str): The path to the Markdown file to be updated.
    - ocr_text (str): The OCR text to be added to the file's YAML front matter.

    Note:
    - This function directly modifies the content of the file specified by `md_file`.
    - The OCR text is added to or replaces the "OCR:" property within the YAML front matter.
    """
    # Read the existing content of the file
    with open(md_file, 'r') as file:
        existing_content = file.read()
    
    # Check if there's an existing YAML front matter (LLM Generated Regex)
    front_matter_match = re.search(r'^---\n(.*?)\n---', existing_content, re.DOTALL)
    
    if front_matter_match:
        # Extract existing front matter
        front_matter = front_matter_match.group(1)
        
        # Check if OCR property exists
        if 'OCR:' in front_matter:
            # Replace existing OCR property with updated value (LLM Generated Regex)
            updated_front_matter = re.sub(
                r'(OCR:\s*").*(")',
                lambda match: match.group(1) + ocr_text + match.group(2),
                front_matter
            )
        else:
            # Append the OCR property, enclosing ocr_text in quotation marks
            updated_front_matter = front_matter + f'\nOCR: "{ocr_text}"'
        
        # Use the escaped string in re.sub (LLM Generated Regex)
        updated_content = re.sub(r'^---\n(.*?)\n---', '---\n' + updated_front_matter + '\n---', existing_content, 1, re.DOTALL)
    else:
        # If no YAML front matter, prepend one with the OCR property, enclosing ocr_text in quotation marks
        ocr_block = f"---\nOCR: \"{ocr_text}\"\n---\n"
        updated_content = ocr_block + existing_content
    
    # Write the updated content back to the file
    with open(md_file, 'w') as file:
        file.write(updated_content)



def find_linked_attachment(md_path: str, image_link: str) -> str:
    """
    Construct the file path for an image linked in a Markdown document.

    This function generates the absolute path to an image file linked within an Obsidian document,
    based on the document's path and the image link provided. If the image link does not contain the
    attachment folder's name, the function assumes the image is stored in a default resource folder
    specific to the Obsidian document. This default resource folder is named after the document
    (with spaces replaced by underscores) and appended with ".resources", located within a global
    attachment folder. If the image link contains the attachment folder's name, the function
    constructs the path by excluding any overlapping parts of the path in the image link and the
    Markdown document's path.

    Parameters:
    - md_path (str): The file path of the Markdown document.
    - image_link (str): The relative or partial path to the image as linked in the Markdown document.

    Returns:
    - str: The absolute file path to the linked image.

    Note:
    - `ATTACHMENT_FOLDER` is a global variable that specifies the name of the folder used to store
      attachments (e.g., images) related to Markdown documents.
    - This function assumes that the Markdown document and its attachments are stored within the
      same parent directory structure.
    """
    if ATTACHMENT_FOLDER not in image_link:
        return os.path.dirname(md_path)+"/"+ATTACHMENT_FOLDER+"/"+str(os.path.splitext(os.path.basename(md_path))[0]).replace(" ","_")+".resources/"+os.path.basename(image_link)
    else:
        return os.path.dirname(md_path)+'/'+'/'.join([i for i in image_link.split('/') if unicodedata.normalize('NFD', i) not in [unicodedata.normalize('NFD', part) for part in md_path.split('/')]])



def process_markdown_file(md_file: str) -> None:
    """
    Process a Markdown file to extract text from linked images using OCR and update the file.

    This function takes a path to a Markdown file, extracts all image links from it, and uses Optical
    Character Recognition (OCR) to extract text from these images. The OCR results are then aggregated
    and used to update the Markdown file.

    The function operates concurrently, processing up to five images in parallel to improve performance.
    After extracting text from all linked images, it aggregates the results into a single string. If any
    text was successfully extracted from the images, the Markdown file is updated with this text.

    Parameters:
    - md_file (str): The path to the Markdown file to be processed.

    Note:
    - The function relies on `extract_image_links` to find image links within the Markdown file.
    - `perform_ocr` is used to extract text from the images linked in the Markdown file.
    - `find_linked_attachment` constructs the path to the image file based on its link in the Markdown.
    - `update_markdown_file` is used to update the Markdown file with the extracted text.
    - The function uses a ThreadPoolExecutor to process up to five images in parallel.
    """
    image_links = extract_image_links(md_file, OVERWRITE_OCR)
    ocr_texts = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Create a future for each image processing task
        future_to_image = {executor.submit(perform_ocr, find_linked_attachment(md_file, link)): link for link in image_links}
        for future in as_completed(future_to_image):
            ocr_texts.append(future.result())
    # Aggregate OCR text results
    ocr_text = "".join(str(text) if text is not None else '' for text in ocr_texts)
    if ocr_text:
        update_markdown_file(md_file, ocr_text)



def main():
    """
    Main function to process all Markdown files in a specified vault path for OCR.

    This function finds all Markdown files within a predefined vault path and processes each file
    concurrently using a ThreadPoolExecutor. The processing involves extracting text from images
    linked in the Markdown files using Optical Character Recognition (OCR) and updating the files
    with the extracted text.

    The function utilizes a ThreadPoolExecutor to manage a pool of worker threads, allowing up to
    five Markdown files to be processed in parallel. This parallel processing is aimed at improving
    the efficiency and speed of the OCR operation across multiple files.

    The progress of the file processing is displayed in real-time using tqdm, providing a visual
    progress bar in the console. This feedback is valuable for understanding the progress of the
    operation, especially when processing a large number of files.

    Note:
    - VAULT_PATH is a global variable that specifies the path to the vault (directory) containing
      the Markdown files to be processed.
    - process_markdown_file is the function called by each worker thread to process a single Markdown
      file. It is responsible for extracting text from images within the file and updating the file
      accordingly.
    """
    markdown_files = list_markdown_files(VAULT_PATH)
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all markdown files for processing
        list(tqdm(executor.map(process_markdown_file, markdown_files), total=len(markdown_files), desc="Processing Markdown Files", unit="md"))
if __name__ == "__main__":
    main()

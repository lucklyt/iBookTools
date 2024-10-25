from operator import ne
import os
import shutil
import zipfile
import argparse
from bs4 import BeautifulSoup, NavigableString
from tqdm import tqdm

# Global variable to determine if a link to jump back to the footnote is needed
need_jump = False
# Global variable to determine if the script should automatically find footnote tags
auto_find_footnote_tags = True
# List of some possible selectors to obtain footnotes
foot_ref_tags_selectors = ['a.footnote-ref', 'a.footnote', 'a.footnote-backref', 'a.footnote-ref',
                           'span.math-super > a', 'a.footnote-link', 'sup.suptext > a']
# Default footnote selector
selector = 'a.footnote-ref'


def extract_epub(epub_path, extract_to):
    """
    Extracts the contents of an EPUB file to a specified directory.

    Parameters:
    - epub_path (str): The path to the EPUB file.
    - extract_to (str): The directory to extract the contents to.

    Returns:
    None
    """
    # Create a temporary directory for extracting the EPUB file
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)
    # If the directory already exists, delete and recreate it
    else:
        shutil.rmtree(extract_to)
        os.makedirs(extract_to)
    # Extract the EPUB file to the directory
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def create_popup_footnotes(html_content):
    """
    Create popup footnotes in the given HTML content.

    Args:
        html_content (str): The HTML content to process.

    Returns:
        str: The modified HTML content with popup footnotes.

    Raises:
        None
    """
    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    # Add the epub namespace if it doesn't exist
    if not 'xmlns:epub' in soup.html.attrs:
        soup.html['xmlns:epub'] = "http://www.idpf.org/2007/ops"
    # Find all footnote references in the HTML content
    footrefs = []
    if auto_find_footnote_tags:
        for selector in foot_ref_tags_selectors:
            footrefs += soup.select(selector)
    else:
        footrefs = soup.select(
            selector)  # Select all <a> tags with class="footnote"，you can change the class name to fit your need
    if not footrefs:
        print('No footnotes found in the document.')
        return html_content
    else:
        print(f"Found {len(footrefs)} footnotes in the document.")
        # Create a progress bar
        pbar = tqdm(total=len(footrefs), desc="Processing footnotes", ncols=80, bar_format='{l_bar}{bar}| {elapsed}')
        processed_notes = 0

    # Process each footnote reference
    for idx, noteref in enumerate(footrefs, start=1):  # idx=1
        note_href = noteref['href']  # "text00004.html#Z1_1"
        noteref['id'] = 'nootref' + str(idx)
        note_id = note_href.split('#')[-1]  # "Z1_1"
        note_text = soup.find(id=note_id)
        if not note_text:
            continue
        noteref['epub:type'] = 'noteref'
        noteref.string = "㊟"
        note_text.name = 'aside'
        note_text['epub:type'] = 'footnote'

        # Replace the content of the <aside> with the text content of its parent <p>
        parent_p = note_text.find_parent('p')
        if parent_p:
            direct_text_nodes = [item for item in parent_p.children if isinstance(item, NavigableString)]
            direct_text = ''.join(direct_text_nodes).strip()
            note_text.string = direct_text
            # for item in direct_text_nodes:
            #     item.replace_with('') # Remove the text of p
            parent_p.insert_after(note_text)
            parent_p.extract()

        # If need_jump is True, add a link to jump back to the footnote reference
        if need_jump:
            new_tag = soup.new_tag('a', href="#" + noteref['id'])
            new_tag.string = '[%d]' % (idx)
            note_text.insert_before(new_tag)
        # Update the progress bar
        pbar.update(1)
        processed_notes += 1

    # Remove all <p> elements with class "note"
    for note in soup.find_all('p', class_='note'):
        note.decompose()

    # Close the progress bar
    pbar.close()
    print(f"Processed {processed_notes} footnotes.")
    return str(soup)


def repack_epub(extract_to, epub_path):
    """
    Repacks the extracted contents of an EPUB file into a new EPUB file.

    Parameters:
    extract_to (str): The path to the directory containing the extracted contents.
    epub_path (str): The path to the original EPUB file.

    Returns:
    None
    """
    # Create a new EPUB file and add the extracted contents to it
    with zipfile.ZipFile(epub_path, 'w') as zip_ref:
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, extract_to)
                zip_ref.write(file_path, arcname=arcname)
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                arcname = os.path.relpath(dir_path, extract_to)
                zip_ref.write(dir_path, arcname=arcname)


def find_and_replace_footnotes(epub_path):
    """
    Finds and replaces footnotes in an EPUB file.

    Args:
        epub_path (str): The path to the EPUB file.

    Returns:
        None
    """
    # Temporary directory for extracting the EPUB file
    extract_to = './extracted_epub'
    extract_epub(epub_path, extract_to)

    # Iterate over all files in the extracted directory
    for root, dirs, files in os.walk(extract_to):
        for file in files:
            if file.endswith('html'):
                file_path = os.path.join(root, file)

                # Read the HTML file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Create popup footnotes
                new_content = create_popup_footnotes(content)

                # Write the modified content back to the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
    print('All footnotes have been processed.')
    # Repack the modified files into an EPUB file
    repack_epub(extract_to, epub_path)
    # Delete the temporary directory
    # for root, dirs, files in os.walk(extract_to, topdown=False):
    #     for file in files:
    #         os.remove(os.path.join(root, file))
    #     for dir in dirs:
    #         os.rmdir(os.path.join(root, dir))


if __name__ == "__main__":
    # Create a parser
    parser = argparse.ArgumentParser(description='Process an EPUB file.')
    # Add a command line argument
    parser.add_argument('epub_file_path', type=str, help='The path to the EPUB file.')
    parser.add_argument('--need_jump', type=bool, help='Whether to add a link to jump back to the footref.',
                        required=False, default=False)
    parser.add_argument('--auto_find_footnote_tags', type=bool, help='Whether to automatically find footnote tags.',
                        required=False, default=True)
    parser.add_argument('--footnote_tags', type=str, help='The CSS selector for the footnote tags.', required=False,
                        default='a.footnote-ref')
    # Parse the command line arguments
    args = parser.parse_args()
    need_jump = args.need_jump
    auto_find_footnote_tags = args.auto_find_footnote_tags
    selector = args.footnote_tags
    # Use the command line arguments
    find_and_replace_footnotes(args.epub_file_path)

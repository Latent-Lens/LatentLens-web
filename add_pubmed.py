#!/usr/bin/env python3
"""
NCBI PubMed ID Fetcher Utility for LatentLens Publications
Usage: python add_pubmed.py <PMID> [abbr]
Example: python add_pubmed.py 38289456 Methods
"""

import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLICATIONS_MD = ROOT / "data" / "publications.md"

def fetch_pubmed(pmid):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"Error fetching data from PubMed API: {e}", file=sys.stderr)
        sys.exit(1)
        
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"Error parsing XML response: {e}", file=sys.stderr)
        sys.exit(1)
        
    article = root.find(".//PubmedArticle")
    if article is None:
        print(f"No publication found for PMID: {pmid}", file=sys.stderr)
        sys.exit(1)
        
    # 1. Title
    title_el = article.find(".//ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else "Unknown Title"
    # Remove trailing period if present
    if title.endswith("."):
        title = title[:-1].strip()
        
    # 2. Authors
    authors = []
    author_list = article.findall(".//AuthorList/Author")
    for author in author_list:
        last = author.find("LastName")
        fore = author.find("ForeName")
        initials = author.find("Initials")
        
        last_name = last.text.strip() if last is not None and last.text else ""
        
        if fore is not None and fore.text:
            first_name = fore.text.strip()
        elif initials is not None and initials.text:
            first_name = initials.text.strip()
        else:
            first_name = ""
            
        if last_name:
            if first_name:
                authors.append(f"{first_name} {last_name}")
            else:
                authors.append(last_name)
                
    authors_str = ", ".join(authors) if authors else "Unknown Authors"
    
    # 3. Journal / Venue
    journal_el = article.find(".//Journal/Title")
    if journal_el is None:
        journal_el = article.find(".//Journal/ISOAbbreviation")
    journal = journal_el.text.strip() if journal_el is not None and journal_el.text else "Unknown Journal"
    
    # 4. Year
    year = "0"
    year_el = article.find(".//JournalIssue/PubDate/Year")
    if year_el is not None and year_el.text:
        year = year_el.text.strip()
    else:
        # Try DateCompleted or MedlineDate string
        date_str_el = article.find(".//JournalIssue/PubDate/MedlineDate")
        if date_str_el is not None and date_str_el.text:
            match = re.search(r"\b(19|20)\d{2}\b", date_str_el.text)
            year = match.group(0) if match else "0"
        else:
            # Fallback to DateCompleted
            date_comp = article.find(".//DateCompleted/Year")
            if date_comp is not None and date_comp.text:
                year = date_comp.text.strip()
            
    # 5. Volume, Issue, Pages
    volume_el = article.find(".//JournalIssue/Volume")
    volume = volume_el.text.strip() if volume_el is not None and volume_el.text else ""
    
    issue_el = article.find(".//JournalIssue/Issue")
    issue = issue_el.text.strip() if issue_el is not None and issue_el.text else ""
    
    pages_el = article.find(".//Pagination/MedlinePgn")
    pages = pages_el.text.strip() if pages_el is not None and pages_el.text else ""
    
    # 6. DOI
    doi = ""
    article_ids = article.findall(".//ArticleIdList/ArticleId")
    for aid in article_ids:
        if aid.attrib.get("IdType") == "doi":
            doi = aid.text.strip() if aid.text else ""
            break
            
    # 7. Abstract
    abstract_paragraphs = []
    abstract_text_els = article.findall(".//Abstract/AbstractText")
    for el in abstract_text_els:
        label = el.attrib.get("Label")
        text = "".join(el.itertext()).strip()
        if text:
            if label:
                abstract_paragraphs.append(f"**{label}**: {text}")
            else:
                abstract_paragraphs.append(text)
                
    abstract = "\n\n".join(abstract_paragraphs) if abstract_paragraphs else "Abstract not available."
    
    return {
        "title": title,
        "authors": authors_str,
        "journal": journal,
        "year": year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "doi": doi,
        "pmid": pmid,
        "abstract": abstract,
        "first_author_last": authors[0].split()[-1] if authors else "Unknown"
    }

def generate_bibtex(info):
    first_author_clean = re.sub(r"[^a-zA-Z]", "", info["first_author_last"]).lower()
    title_keyword = re.sub(r"[^a-zA-Z]", "", info["title"].split()[0]).lower() if info["title"].split() else "study"
    cite_key = f"{first_author_clean}{info['year']}{title_keyword}"
    
    bib_authors = " and ".join(info["authors"].split(", "))
    
    bib = []
    bib.append(f"@article{{{cite_key},")
    bib.append(f"  title={{{info['title']}}},")
    bib.append(f"  author={{{bib_authors}}},")
    bib.append(f"  journal={{{info['journal']}}},")
    if info["volume"]:
        bib.append(f"  volume={{{info['volume']}}},")
    if info["issue"]:
        bib.append(f"  number={{{info['issue']}}},")
    if info["pages"]:
        bib.append(f"  pages={{{info['pages']}}},")
    bib.append(f"  year={{{info['year']}}}")
    bib.append("}")
    return "\n".join(bib)

def append_to_publications(info, abbr="Methods"):
    bibtex = generate_bibtex(info)
    
    entry = []
    entry.append(f"\n## {info['title']}")
    entry.append(f"year: {info['year']}")
    entry.append(f"authors: {info['authors']}")
    entry.append(f"journal: {info['journal']}")
    if info["volume"]:
        entry.append(f"volume: {info['volume']}")
    if info["issue"]:
        entry.append(f"issue: {info['issue']}")
    if info["pages"]:
        entry.append(f"pages: {info['pages']}")
    if info.get("doi"):
        entry.append(f"doi: {info['doi']}")
    if info.get("pmid"):
        entry.append(f"pmid: {info['pmid']}")
    if abbr:
        entry.append(f"abbr: {abbr}")
    if info.get("doi"):
        entry.append(f"html: https://doi.org/{info['doi']}")
    
    entry.append("bibtex: |")
    indented_bib = "\n".join(f"  {line}" for line in bibtex.splitlines())
    entry.append(indented_bib)
    
    entry.append("---")
    entry.append(info["abstract"])
    entry.append("")
    
    # Read existing content to make sure we append cleanly
    content = PUBLICATIONS_MD.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        content += "\n"
        
    new_entry = "\n".join(entry)
    PUBLICATIONS_MD.write_text(content + new_entry + "\n", encoding="utf-8", newline="\n")
    print(f"Successfully added '{info['title']}' to {PUBLICATIONS_MD.name}!")

def main():
    if len(sys.argv) < 2:
        print("Usage: python add_pubmed.py <PMID> [abbr]")
        print("Example: python add_pubmed.py 38289456 Methods")
        sys.exit(1)
        
    pmid = sys.argv[1].strip()
    abbr = sys.argv[2].strip() if len(sys.argv) > 2 else "Paper"
    
    print(f"Fetching PubMed ID: {pmid}...")
    info = fetch_pubmed(pmid)
    append_to_publications(info, abbr)

if __name__ == "__main__":
    main()

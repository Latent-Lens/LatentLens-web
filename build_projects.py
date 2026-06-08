from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html import escape
from pathlib import Path
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
PROJECTS_MD = ROOT / "data" / "projects.md"
PROJECTS_INDEX = ROOT / "pages" / "projects.html"
PROJECTS_DIR = ROOT / "pages" / "projects"
REPOSITORIES_INDEX = ROOT / "pages" / "repositories.html"
HOME_INDEX = ROOT / "index.html"
ROBOTS_TXT = ROOT / "robots.txt"
SITEMAP_XML = ROOT / "sitemap.xml"
PUBLICATIONS_MD = ROOT / "data" / "publications.md"
PUBLICATIONS_INDEX = ROOT / "pages" / "publications.html"
PMIDS_TXT = ROOT / "data" / "pmids.txt"
PUBMED_CACHE_JSON = ROOT / "data" / "pubmed_cache.json"


@dataclass
class Project:
    id: str
    body: str
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key, default)

    @property
    def tags(self) -> list[str]:
        return [tag.strip() for tag in self.get("tags").split(",") if tag.strip()]

    @property
    def slug(self) -> str:
        return self.get("slug", self.id)

    @property
    def detail_url(self) -> str:
        return self.get("detailUrl", f"projects/{self.slug}.html")


def clean_page_path(page_name: str) -> str:
    return f"/{page_name}"


def clean_project_path(project: Project) -> str:
    path = Path(project.detail_url)
    return f"/projects/{path.stem}"


def absolute_url(path: str) -> str:
    if path == "/":
        return "https://latentlens.org/"
    return f"https://latentlens.org{path}"


def parse_projects(markdown: str) -> list[Project]:
    blocks = re.split(r"\n## ", markdown)
    projects: list[Project] = []

    for block in blocks[1:]:
        normalized = block[3:] if block.startswith("## ") else block
        meta_text, _, body = normalized.partition("\n---\n")
        lines = [line for line in meta_text.strip().splitlines() if line.strip()]
        if not lines:
            continue

        fallback_id = lines[0].strip()
        fields: dict[str, str] = {}

        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

        projects.append(Project(id=fields.get("slug", fallback_id), body=body.strip(), fields=fields))

    return projects


def badge_class(status: str) -> str:
    normalized = status.lower().strip()
    if normalized == "active":
        return "status-active"
    if normalized == "in design":
        return "status-design"
    if normalized in ("complete", "published"):
        return "status-complete"
    if normalized == "in progress":
        return "status-progress"
    return ""


def asset_path(path: str, prefix: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/", "//")):
        return path
    return f"{prefix}{path}"


def render_tags(project: Project) -> str:
    tag_badges = "".join(f'<span class="project-badge">{escape(tag)}</span>' for tag in project.tags)
    if tag_badges:
        return f'<span class="project-badge-row">{tag_badges}</span>'
    return ""


def strip_markdown(text: str) -> str:
    if not text:
        return ""
    # Strip links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Strip bold **text** -> text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # Strip italics *text* -> text
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    return text


def render_inline_markdown(text: str) -> str:
    if not text:
        return ""
    escaped = escape(text)
    # Simple link parsing (e.g., [text](url))
    escaped = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped
    )
    # Simple bold parsing (e.g., **text**)
    escaped = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped)
    # Simple italic/emphasis parsing (e.g., *text*)
    escaped = re.sub(r'\*(.*?)\*', r'<em>\1</em>', escaped)
    return escaped


def has_valid_image(project: Project) -> bool:
    image_path_str = project.get("image")
    if not image_path_str:
        return False
    return (ROOT / image_path_str).is_file()


def render_project_card(project: Project, asset_prefix: str = "/") -> str:
    title = render_inline_markdown(project.get("title"))
    url = escape(clean_project_path(project))
    image = asset_path(project.get("image"), asset_prefix)
    thumb_class = escape(project.get("thumbClass", "project-thumb-blue"))
    thumb_text = escape(project.get("thumbText"))

    # Split status by comma
    status_raw = project.get("status")
    status_list = [s.strip() for s in status_raw.split(",") if s.strip()] if status_raw else []
    status_badges = []
    for s in status_list:
        s_class = badge_class(s)
        status_badges.append(f'<span class="project-badge {s_class}">{escape(s)}</span>')
    status_html = ""
    if status_badges:
        status_html = f'<span class="project-badge-row">{"".join(status_badges)}</span>'

    image_html = ""
    if has_valid_image(project):
        image_html = f'\n              <img class="project-image" src="{escape(image)}" alt="" />'
    thumb_text_html = f"<span>{thumb_text}</span>" if thumb_text else ""

    tags_html = render_tags(project)
    meta_stacked = " project-meta-stacked" if tags_html else ""

    return f"""          <article class="project-card">
            <a class="project-thumb-link" href="{url}" aria-label="{title}">
              <div class="project-thumb {thumb_class}" aria-hidden="true">{thumb_text_html}</div>{image_html}
            </a>
            <div class="project-content">
              <div class="project-title-row">
                <h2><a href="{url}">{title}</a></h2>
                <div class="project-meta{meta_stacked}">
                  {status_html}
                  {tags_html}
                </div>
              </div>
              <p>{render_inline_markdown(project.get("summary"))}</p>
              <a class="read-more" href="{url}">Read More →</a>
            </div>
          </article>"""


@dataclass
class Publication:
    id: str
    body: str
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key, default)

    @property
    def year(self) -> int:
        try:
            return int(self.get("year", "0"))
        except ValueError:
            return 0


def parse_publications(markdown: str) -> list[Publication]:
    blocks = re.split(r"\n## ", markdown)
    publications: list[Publication] = []

    for block in blocks[1:]:
        normalized = block[3:] if block.startswith("## ") else block
        meta_text, _, body = normalized.partition("\n---\n")
        lines = [line for line in meta_text.strip().splitlines() if line.strip()]
        if not lines:
            continue

        fallback_title = lines[0].strip()
        fields: dict[str, str] = {}
        fields["title"] = fallback_title

        current_key = None
        bibtex_lines = []
        is_in_bibtex = False

        for line in lines[1:]:
            if line.startswith("bibtex:"):
                current_key = "bibtex"
                is_in_bibtex = True
                continue

            if is_in_bibtex:
                bibtex_lines.append(line)
            else:
                if ":" in line:
                    k, v = line.split(":", 1)
                    fields[k.strip()] = v.strip()

        if is_in_bibtex:
            raw_bib = "\n".join(bibtex_lines).strip()
            if raw_bib.startswith("|"):
                raw_bib = raw_bib[1:].strip()
            fields["bibtex"] = raw_bib

        publications.append(Publication(id=fields.get("title", fallback_title), body=body.strip(), fields=fields))

    return publications


def render_publication_item(pub: Publication, index: int) -> str:
    title = pub.get("title")
    authors_raw = pub.get("authors")

    # Extract DOI & PMID
    html = pub.get("html")
    pdf = pub.get("pdf")
    doi_val = pub.get("doi")
    if not doi_val and html and "doi.org/" in html:
        doi_val = html.split("doi.org/")[-1].strip()
        
    pmid_val = pub.get("pmid")

    # Format title as a link if a URL is available
    title_url = html or pdf
    if title_url:
        title_html = f'<h3 class="pub-title"><a href="{escape(title_url)}" target="_blank" rel="noopener noreferrer">{render_inline_markdown(title)}</a></h3>'
    else:
        title_html = f'<h3 class="pub-title">{render_inline_markdown(title)}</h3>'

    # Format authors with equal contribution circled i and bold group name
    author_list = [a.strip() for a in authors_raw.split(",") if a.strip()]
    has_equal_contrib = pub.get("equal_contribution", "").lower() in ("true", "yes", "1")
    if "*" in authors_raw:
        has_equal_contrib = True

    formatted_authors = []
    for author in author_list:
        clean_author = author
        is_co_first = False
        if author.endswith("*"):
            clean_author = author[:-1].strip()
            is_co_first = True

        is_group = "LatentLens Research Group" in clean_author
        author_classes = ["author-name"]
        if is_group:
            author_classes.append("group-author")

        author_name_esc = escape(clean_author)
        author_inner = f"<strong>{author_name_esc}</strong>" if is_group else author_name_esc

        if is_co_first:
            author_inner += "<span>*</span>"

        formatted_authors.append(f'<span class="{" ".join(author_classes)}">{author_inner}</span>')

    authors_str = ", ".join(formatted_authors)
    if has_equal_contrib:
        authors_str += ' <span class="co-first" title="Equal contribution">ⓘ</span>'

    venue = escape(pub.get("journal"))
    volume = pub.get("volume")
    issue = pub.get("issue")
    pages = pub.get("pages")
    year = pub.get("year")

    venue_details = []
    if venue:
        venue_details.append(venue)
    if volume:
        venue_details.append(f"vol. {escape(volume)}")
    if issue:
        venue_details.append(f"no. {escape(issue)}")
    if pages:
        venue_details.append(f"pp. {escape(pages)}")
    if year:
        venue_details.append(escape(year))

    venue_str = ", ".join(venue_details)

    buttons = []
    abstract_id = f"pub-abstract-{index}"
    if pub.body:
        buttons.append(f'<button class="pub-btn" data-toggle-target="{abstract_id}">Abstract</button>')

    # Determine DOI vs HTML button
    if doi_val:
        buttons.append(f'<a href="https://doi.org/{escape(doi_val)}" class="pub-btn pub-btn-link" target="_blank" rel="noopener noreferrer">DOI</a>')
    elif html:
        buttons.append(f'<a href="{escape(html)}" class="pub-btn pub-btn-link" target="_blank" rel="noopener noreferrer">HTML</a>')

    bibtex_id = f"pub-bibtex-{index}"
    bibtex_content = pub.get("bibtex")
    if bibtex_content:
        buttons.append(f'<button class="pub-btn" data-toggle-target="{bibtex_id}">Bib</button>')

    if pdf:
        buttons.append(f'<a href="{escape(pdf)}" class="pub-btn pub-btn-link" target="_blank" rel="noopener noreferrer">PDF</a>')

    code = pub.get("code")
    if code:
        buttons.append(f'<a href="{escape(code)}" class="pub-btn pub-btn-link" target="_blank" rel="noopener noreferrer">Code</a>')

    buttons_html = f'\n              <div class="pub-btn-row">{" ".join(buttons)}</div>' if buttons else ""

    # Generate Altmetric and Dimensions badges if possible
    badges = []
    
    # 1. Check for explicit Shields.io badges first
    altmetric_count = pub.get("altmetric")
    scholar_count = pub.get("scholar")
    citations_count = pub.get("citations") or pub.get("dimensions")
    inspire_count = pub.get("inspire")

    if altmetric_count:
        # Shields.io Altmetric badge
        badges.append(f'<a href="https://www.altmetric.com" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/Altmetric-{escape(altmetric_count)}-lightgrey?style=flat&logo=altmetric" alt="Altmetric {escape(altmetric_count)}" style="height: 20px; border-radius: 4px; vertical-align: middle;"></a>')
    
    if citations_count:
        # Shields.io Citations badge
        badges.append(f'<a href="https://dimensions.ai" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/Citations-{escape(citations_count)}-darkgreen?style=flat" alt="Citations {escape(citations_count)}" style="height: 20px; border-radius: 4px; vertical-align: middle;"></a>')

    if scholar_count:
        # Shields.io Google Scholar badge
        scholar_url = pub.get("scholar_url") or "#"
        badges.append(f'<a href="{escape(scholar_url)}" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/scholar-{escape(scholar_count)}-blue?style=flat" alt="Google Scholar {escape(scholar_count)}" style="height: 20px; border-radius: 4px; vertical-align: middle;"></a>')

    if inspire_count:
        # Shields.io Inspire-HEP badge
        badges.append(f'<a href="https://inspirehep.net" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/inspire-{escape(inspire_count)}-black?style=flat" alt="Inspire-HEP {escape(inspire_count)}" style="height: 20px; border-radius: 4px; vertical-align: middle;"></a>')

    # 2. If no explicit badges, fall back to live embeds if DOI/PMID is present
    if not badges:
        if doi_val:
            badges.append(f'<div class="altmetric-embed" data-badge-type="4" data-condensed="true" data-hide-no-mentions="true" data-doi="{escape(doi_val)}"></div>')
            badges.append(f'<span class="__dimensions_badge_embed__" data-doi="{escape(doi_val)}" data-style="small_rectangle" data-hide-zero-citations="true"></span>')
        elif pmid_val:
            badges.append(f'<div class="altmetric-embed" data-badge-type="4" data-condensed="true" data-hide-no-mentions="true" data-pmid="{escape(pmid_val)}"></div>')
            badges.append(f'<span class="__dimensions_badge_embed__" data-pmid="{escape(pmid_val)}" data-style="small_rectangle" data-hide-zero-citations="true"></span>')

    badges_html = f'\n              <div class="pub-badges">{" ".join(badges)}</div>' if badges else ""

    panels = []
    if pub.body:
        panels.append(f"""
              <div id="{abstract_id}" class="pub-toggle-panel" hidden>
                <p class="pub-abstract-text">{render_inline_markdown(pub.body)}</p>
              </div>""")

    if bibtex_content:
        panels.append(f"""
              <div id="{bibtex_id}" class="pub-toggle-panel" hidden>
                <pre class="pub-bibtex-code"><code>{escape(bibtex_content)}</code></pre>
              </div>""")

    panels_html = "".join(panels)

    abbr = pub.get("abbr")
    if abbr:
        abbr_class = f"abbr-{abbr.lower()}"
        abbr_html = f'<div class="pub-left"><span class="abbr {escape(abbr_class)}">{escape(abbr)}</span></div>'
    else:
        abbr_html = '<div class="pub-left"></div>'

    return f"""          <li class="pub-item">
            {abbr_html}
            <div class="pub-body">
              {title_html}
              <p class="pub-authors">{authors_str}</p>
              <p class="pub-journal">{venue_str}</p>{buttons_html}{badges_html}{panels_html}
            </div>
          </li>"""


def render_publications_list(publications: list[Publication]) -> str:
    by_year: dict[int, list[Publication]] = {}
    for pub in publications:
        by_year.setdefault(pub.year, []).append(pub)

    sections = []
    sorted_years = sorted(by_year.keys(), reverse=True)

    global_index = 0
    for year in sorted_years:
        pubs = by_year[year]
        items_html = []
        for pub in pubs:
            items_html.append(render_publication_item(pub, global_index))
            global_index += 1

        list_html = "\n".join(items_html)
        year_header = str(year) if year > 0 else "Preprints & Other"

        sections.append(f"""        <div class="pub-year-section">
          <h2 class="pub-year-header">{year_header}</h2>
          <ol class="pub-list">
{list_html}
          </ol>
        </div>""")

    return "\n\n".join(sections)


def render_project_list(projects: list[Project]) -> str:
    cards = "\n\n".join(render_project_card(project) for project in projects)
    return f'        <div class="project-grid">\n{cards}\n        </div>'


def render_markdown_body(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    html_blocks = []
    in_list = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            if in_list:
                html_blocks.append("        </ul>")
                in_list = False
            continue

        # Handle headings
        if line_strip.startswith("### "):
            if in_list:
                html_blocks.append("        </ul>")
                in_list = False
            heading_text = line_strip[4:].strip()
            html_blocks.append(f"        <h3>{render_inline_markdown(heading_text)}</h3>")
        elif line_strip.startswith("## "):
            if in_list:
                html_blocks.append("        </ul>")
                in_list = False
            heading_text = line_strip[3:].strip()
            html_blocks.append(f"        <h2>{render_inline_markdown(heading_text)}</h2>")
        # Handle list items
        elif line_strip.startswith("- ") or line_strip.startswith("* "):
            if not in_list:
                html_blocks.append("        <ul>")
                in_list = True
            item_text = line_strip[2:].strip()
            html_blocks.append(f"          <li>{render_inline_markdown(item_text)}</li>")
        else:
            if in_list:
                html_blocks.append("        </ul>")
                in_list = False
            html_blocks.append(f"        <p>{render_inline_markdown(line_strip)}</p>")

    if in_list:
        html_blocks.append("        </ul>")

    return "\n".join(html_blocks)


def render_project_detail(project: Project, asset_prefix: str = "/") -> str:
    image = asset_path(project.get("image"), asset_prefix)
    image_html = ""
    if has_valid_image(project):
        image_html = f"""

        <figure class="project-hero">
          <img src="{escape(image)}" alt="" />
        </figure>"""

    return f"""        <p class="breadcrumb"><a href="/projects">projects</a> / {escape(project.slug)}</p>
        <div class="post-header">
          <h1>{render_inline_markdown(project.get("title"))}</h1>{image_html}
        </div>

{render_markdown_body(project.body)}"""


def replace_between_markers(html: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?P<indent>[ \t]*){re.escape(start)}.*?^[ \t]*{re.escape(end)}",
        re.DOTALL | re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return f"{indent}{start}\n{replacement}\n{indent}{end}"

    updated, count = pattern.subn(repl, html)
    if count != 1:
        raise RuntimeError(f"Expected one marker block for {start}, found {count}")
    return updated


def write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def generate_sitemap(projects: list[Project]) -> str:
    today = date.today().isoformat()
    urls = [
        "/",
        clean_page_path("projects"),
        clean_page_path("publications"),
        clean_page_path("repositories"),
    ]
    urls.extend(clean_project_path(project) for project in projects)

    entries = "\n".join(
        f"""  <url>
    <loc>{absolute_url(path)}</loc>
    <lastmod>{today}</lastmod>
  </url>"""
        for path in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""


def generate_redirects(projects: list[Project]) -> str:
    rules = [
        "/index.html / 301",
        "/pages/projects.html /projects 301",
        "/pages/publications.html /publications 301",
        "/pages/repositories.html /repositories 301",
    ]
    rules.extend(
        f"/pages/projects/{Path(project.detail_url).name} {clean_project_path(project)} 301"
        for project in projects
    )
    return "\n".join(rules) + "\n"


def export_site(projects: list[Project]) -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()

    for source, destination in [
        (HOME_INDEX, OUT_DIR / "index.html"),
        (PROJECTS_INDEX, OUT_DIR / "projects.html"),
        (PUBLICATIONS_INDEX, OUT_DIR / "publications.html"),
        (REPOSITORIES_INDEX, OUT_DIR / "repositories.html"),
        (ROBOTS_TXT, OUT_DIR / "robots.txt"),
        (SITEMAP_XML, OUT_DIR / "sitemap.xml"),
    ]:
        shutil.copy2(source, destination)

    for asset in ["styles.css", "script.js"]:
        shutil.copy2(ROOT / asset, OUT_DIR / asset)

    if (ROOT / "public").exists():
        shutil.copytree(ROOT / "public", OUT_DIR / "public")

    out_projects = OUT_DIR / "projects"
    out_projects.mkdir()
    for project in projects:
        source = PROJECTS_DIR / Path(project.detail_url).name
        shutil.copy2(source, out_projects / source.name)

    write_text_if_changed(OUT_DIR / "_redirects", generate_redirects(projects))


def sync_pmids() -> None:
    if not PMIDS_TXT.exists():
        return

    lines = [line.strip() for line in PMIDS_TXT.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return

    import json
    cache = {}
    if PUBMED_CACHE_JSON.exists():
        try:
            cache = json.loads(PUBMED_CACHE_JSON.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    pub_md_content = PUBLICATIONS_MD.read_text(encoding="utf-8") if PUBLICATIONS_MD.exists() else ""
    updated_cache = False

    for line in lines:
        parts = line.split(None, 1)
        pmid = parts[0].strip()
        abbr = parts[1].strip() if len(parts) > 1 else "Paper"

        info = None
        if pmid in cache:
            info = cache[pmid]
        else:
            print(f"Auto-fetching new PubMed ID: {pmid}...")
            try:
                import add_pubmed
                info = add_pubmed.fetch_pubmed(pmid)
                cache[pmid] = info
                updated_cache = True
            except Exception as e:
                print(f"Error fetching PMID {pmid}: {e}", file=sys.stderr)
                continue

        if info:
            title_esc = escape(info["title"])
            if info["title"] not in pub_md_content and title_esc not in pub_md_content:
                print(f"Auto-appending '{info['title']}' to publications.md...")
                try:
                    import add_pubmed
                    add_pubmed.append_to_publications(info, abbr)
                    pub_md_content = PUBLICATIONS_MD.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"Error appending PMID {pmid}: {e}", file=sys.stderr)

    if updated_cache:
        PUBMED_CACHE_JSON.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def build() -> None:
    sync_pmids()
    projects = parse_projects(PROJECTS_MD.read_text(encoding="utf-8"))

    index_html = PROJECTS_INDEX.read_text(encoding="utf-8")
    index_html = replace_between_markers(
        index_html,
        "<!-- PROJECT_LIST_START -->",
        "<!-- PROJECT_LIST_END -->",
        render_project_list(projects),
    )
    write_text_if_changed(PROJECTS_INDEX, index_html)

    template_path = PROJECTS_DIR / "template.html"
    if not template_path.exists():
        raise RuntimeError(f"Master template file does not exist: {template_path}")
    
    template_html = template_path.read_text(encoding="utf-8")

    for project in projects:
        detail_relative = project.detail_url
        if not detail_relative.startswith("projects/"):
            raise RuntimeError(f"Unsupported detailUrl for build: {detail_relative}")

        detail_path = PROJECTS_DIR / Path(detail_relative).name

        detail_html = replace_between_markers(
            template_html,
            "<!-- PROJECT_DETAIL_START -->",
            "<!-- PROJECT_DETAIL_END -->",
            render_project_detail(project),
        )
        project_title = escape(strip_markdown(project.get('title')))
        project_desc = escape(strip_markdown(project.get("summary")))
        project_url = absolute_url(clean_project_path(project))

        detail_html = detail_html.replace("Project Title | LatentLens", f"{project_title} | LatentLens")
        detail_html = detail_html.replace("Project Description", project_desc)
        detail_html = detail_html.replace("https://latentlens.org/projects/placeholder", project_url)

        write_text_if_changed(detail_path, detail_html)

    # Automatically clean up orphaned html files in the projects directory
    valid_filenames = {Path(p.detail_url).name for p in projects}
    valid_filenames.add("template.html")
    
    for path in PROJECTS_DIR.glob("*.html"):
        if path.name not in valid_filenames:
            print(f"Cleaning up orphaned project page: {path.relative_to(ROOT)}")
            path.unlink()

    write_text_if_changed(SITEMAP_XML, generate_sitemap(projects))

    print(f"Built {len(projects)} projects from {PROJECTS_MD.relative_to(ROOT)}")

    # Publications compilation
    if PUBLICATIONS_MD.exists():
        publications = parse_publications(PUBLICATIONS_MD.read_text(encoding="utf-8"))
        
        # Read active PMIDs from pmids.txt to filter rendering
        active_pmids = set()
        if PMIDS_TXT.exists():
            for line in PMIDS_TXT.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    active_pmids.add(line.split()[0].strip())
                    
        # Filter logic
        import json
        cache = {}
        if PUBMED_CACHE_JSON.exists():
            try:
                cache = json.loads(PUBMED_CACHE_JSON.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
                
        filtered_pubs = []
        for pub in publications:
            pub_pmid = pub.get("pmid")
            if not pub_pmid:
                title_lower = pub.get("title", "").strip().lower()
                for cache_pmid, cache_info in cache.items():
                    if cache_info.get("title", "").strip().lower() == title_lower:
                        pub_pmid = cache_pmid
                        break
            if pub_pmid in active_pmids:
                filtered_pubs.append(pub)
                
        pub_html = PUBLICATIONS_INDEX.read_text(encoding="utf-8")
        pub_html = replace_between_markers(
            pub_html,
            "<!-- PUBLICATION_LIST_START -->",
            "<!-- PUBLICATION_LIST_END -->",
            render_publications_list(filtered_pubs),
        )
        write_text_if_changed(PUBLICATIONS_INDEX, pub_html)
        print(f"Built {len(filtered_pubs)} publications (filtered from {len(publications)}) from {PUBLICATIONS_MD.relative_to(ROOT)}")

    export_site(projects)
    print(f"Exported Cloudflare Pages site to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    build()

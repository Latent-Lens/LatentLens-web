from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
PROJECTS_MD = ROOT / "data" / "projects.md"
PROJECTS_INDEX = ROOT / "pages" / "projects.html"
PROJECTS_DIR = ROOT / "pages" / "projects"


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
    normalized = status.lower()
    if normalized == "active":
        return "status-active"
    if normalized == "in design":
        return "status-design"
    if normalized == "complete":
        return "status-complete"
    return ""


def asset_path(path: str, prefix: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/", "//")):
        return path
    return f"{prefix}{path}"


def render_tags(project: Project) -> str:
    tag_badges = "".join(f'<span class="project-badge">{escape(tag)}</span>' for tag in project.tags)
    if len(project.tags) > 1:
        return f'<span class="project-badge-row">{tag_badges}</span>'
    return tag_badges


def render_project_card(project: Project, asset_prefix: str = "../") -> str:
    title = escape(project.get("title"))
    url = escape(project.detail_url)
    image = asset_path(project.get("image"), asset_prefix)
    thumb_class = escape(project.get("thumbClass", "project-thumb-blue"))
    thumb_text = escape(project.get("thumbText"))
    stacked = " project-meta-stacked" if len(project.tags) > 1 else ""
    status = escape(project.get("status"))
    status_class = badge_class(project.get("status"))

    image_html = f'\n              <img class="project-image" src="{escape(image)}" alt="" />' if image else ""
    thumb_text_html = f"<span>{thumb_text}</span>" if thumb_text else ""

    return f"""          <article class="project-card">
            <a class="project-thumb-link" href="{url}" aria-label="{title}">
              <div class="project-thumb {thumb_class}" aria-hidden="true">{thumb_text_html}</div>{image_html}
            </a>
            <div class="project-content">
              <div class="project-title-row">
                <h2><a href="{url}">{title}</a></h2>
                <div class="project-meta{stacked}">
                  <span class="project-badge {status_class}">{status}</span>
                  {render_tags(project)}
                </div>
              </div>
              <p>{escape(project.get("summary"))}</p>
              <p class="project-byline">By: {escape(project.get("byline"))}</p>
              <a class="read-more" href="{url}">Read More →</a>
            </div>
          </article>"""


def render_project_list(projects: list[Project]) -> str:
    cards = "\n\n".join(render_project_card(project) for project in projects)
    return f'        <div class="project-grid">\n{cards}\n        </div>'


def render_markdown_body(markdown: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", markdown) if paragraph.strip()]
    return "\n".join(f"        <p>{escape(paragraph)}</p>" for paragraph in paragraphs)


def render_project_detail(project: Project, asset_prefix: str = "../../") -> str:
    image = asset_path(project.get("image"), asset_prefix)
    image_html = ""
    if image:
        image_html = f"""

        <figure class="project-hero">
          <img src="{escape(image)}" alt="{escape(project.get("imageAlt"))}" />
        </figure>"""

    return f"""        <p class="breadcrumb"><a href="../projects.html">projects</a> / {escape(project.get("title").lower())}</p>
        <div class="post-header">
          <h1>{escape(project.get("title"))}</h1>
          <p>{escape(project.get("subtitle"))}</p>
        </div>{image_html}

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
    if path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8", newline="\n")


def build() -> None:
    projects = parse_projects(PROJECTS_MD.read_text(encoding="utf-8"))

    index_html = PROJECTS_INDEX.read_text(encoding="utf-8")
    index_html = replace_between_markers(
        index_html,
        "<!-- PROJECT_LIST_START -->",
        "<!-- PROJECT_LIST_END -->",
        render_project_list(projects),
    )
    write_text_if_changed(PROJECTS_INDEX, index_html)

    for project in projects:
        detail_relative = project.detail_url
        if not detail_relative.startswith("projects/"):
            raise RuntimeError(f"Unsupported detailUrl for build: {detail_relative}")

        detail_path = PROJECTS_DIR / Path(detail_relative).name
        if not detail_path.exists():
            raise RuntimeError(f"Project detail page does not exist: {detail_path}")

        detail_html = detail_path.read_text(encoding="utf-8")
        detail_html = replace_between_markers(
            detail_html,
            "<!-- PROJECT_DETAIL_START -->",
            "<!-- PROJECT_DETAIL_END -->",
            render_project_detail(project),
        )
        detail_html = re.sub(
            r"<title>.*?</title>",
            f"<title>{escape(project.get('title'))} | LatentLens</title>",
            detail_html,
            count=1,
        )
        detail_html = re.sub(
            r'<meta name="description" content=".*?" />',
            f'<meta name="description" content="{escape(project.get("subtitle"))}" />',
            detail_html,
            count=1,
        )
        write_text_if_changed(detail_path, detail_html)

    print(f"Built {len(projects)} projects from {PROJECTS_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    build()

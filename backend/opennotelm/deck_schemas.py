from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .retrieval import Scope
from .schemas import StrictModel

Text = Annotated[str, Field(min_length=1, max_length=1000)]
EvidenceID = Annotated[str, Field(min_length=1, max_length=80)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
ContentBasis = Literal["source", "interpretation", "background", "analogy"]


class DeckPreferences(StrictModel):
    source_only: bool = False
    chapter_only: bool = False
    include_editorial_notes: bool = False
    dense_text: bool = False


class DeckScope(Scope):
    kind: Literal["selected", "source", "node", "nodes", "knowledge"] = "selected"
    knowledge_page_id: str | None = None

    @model_validator(mode="after")
    def knowledge_identity(self):
        if self.kind == "knowledge" and not self.knowledge_page_id:
            raise ValueError("Knowledge scope needs a page")
        if self.kind != "knowledge" and self.knowledge_page_id:
            raise ValueError("Unexpected knowledge page")
        return self

    def source_scope(self):
        return Scope.model_validate(self.model_dump(exclude={"knowledge_page_id"}))


class DeckInput(StrictModel):
    scope: DeckScope = Field(default_factory=DeckScope)
    slide_count: Literal[10, 15, 20] = 15
    language: str = Field(default="zh-CN", min_length=2, max_length=80)
    instruction: str = Field(default="", max_length=4000)
    render_mode: Literal["generated_page", "native"] = "generated_page"
    title_mode: Literal["auto", "source"] = "auto"


class DeckBatchInput(DeckInput):
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class DeckTitleInput(StrictModel):
    title: str = Field(min_length=1, max_length=1000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()


class DeckBrief(StrictModel):
    topic: str = Field(min_length=1, max_length=200)
    goal: Text
    audience: str = Field(min_length=1, max_length=200)
    language: str = Field(min_length=2, max_length=80)
    slide_count: Literal[10, 15, 20]
    content_principles: list[Text] = Field(min_length=1, max_length=10)


class PlannedSlide(StrictModel):
    index: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=400)
    key_message: str = Field(min_length=1, max_length=500)
    evidence_ids: list[EvidenceID] = Field(min_length=1, max_length=30)
    # Defaults keep saved V1 plans readable; new planning validates these fields.
    teaching_points: list[Annotated[str, Field(min_length=1, max_length=250)]] = Field(
        default_factory=list, max_length=5
    )
    visual_mode: Literal["illustration", "diagram", "typography"] = "diagram"
    visual_concept: str = Field(default="", max_length=500)
    visual_grammar: str = Field(default="", max_length=400)
    # Display units: one CJK character or one Latin word, not a model-token budget.
    reading_budget: int = Field(default=0, ge=0, le=900)


class DeckPlan(StrictModel):
    narrative: str = Field(min_length=1, max_length=3000)
    slides: list[PlannedSlide] = Field(min_length=10, max_length=20)


class Palette(StrictModel):
    background: Color
    text: Color
    accent: Color
    secondary: Color
    muted: Color


class Typography(StrictModel):
    title_family: str = Field(min_length=1, max_length=100)
    body_family: str = Field(min_length=1, max_length=100)
    direction: Text


class Composition(StrictModel):
    density: Literal["low", "medium", "high"]
    whitespace: Text
    rhythm: Text
    hierarchy: Text


class DeckStyleManifest(StrictModel):
    concept: Text
    design_rationale: Text
    palette: Palette
    typography: Typography
    composition: Composition
    image_style: Text
    motifs: list[Text] = Field(max_length=10)
    consistency_rules: list[Text] = Field(min_length=1, max_length=10)


class ElementItem(StrictModel):
    label: str = Field(default="", max_length=200)
    text: str = Field(min_length=1, max_length=1200)
    citations: list[EvidenceID] = Field(default_factory=list, max_length=20)
    basis: ContentBasis | None = None


class SlideContentElement(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    type: Literal[
        "headline",
        "subheadline",
        "body",
        "statement",
        "bullet_list",
        "quote",
        "number",
        "label",
        "comparison",
        "caption",
        "source_note",
    ]
    text: str = Field(default="", max_length=2500)
    label: str = Field(default="", max_length=300)
    items: list[ElementItem] = Field(default_factory=list, max_length=8)
    citations: list[EvidenceID] = Field(default_factory=list, max_length=20)
    # Internal provenance only; never rendered as a heading or extra page text.
    basis: ContentBasis = "source"

    @model_validator(mode="after")
    def semantic_content(self):
        if self.type in ("bullet_list", "comparison"):
            if len(self.items) < (2 if self.type == "comparison" else 1):
                raise ValueError("This element requires structured items")
        elif not self.text.strip():
            raise ValueError("This element requires text")
        return self


class VisualDirection(StrictModel):
    composition_intent: Text
    hierarchy: list[str] = Field(min_length=1, max_length=20)
    visual_balance: Text
    image_role: Text
    background_direction: Text
    emphasis: Text
    density: Literal["low", "medium", "high"]
    mood: Text


class AssetRequest(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    type: Literal["generated_image"] = "generated_image"
    role: Text
    purpose: Text
    subject: Text
    priority: Literal["low", "medium", "high"]


class VisualRelationship(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    source_element: str = Field(min_length=1, max_length=64)
    target_element: str = Field(min_length=1, max_length=64)
    kind: Literal["sequence", "contrast", "association", "cause", "cycle"]
    explanation: str = Field(min_length=1, max_length=400)
    citations: list[EvidenceID] = Field(default_factory=list, max_length=20)
    basis: ContentBasis = "source"


class SlideSpec(StrictModel):
    key_message: str = Field(min_length=1, max_length=500)
    content_elements: list[SlideContentElement] = Field(min_length=1, max_length=16)
    visual_direction: VisualDirection
    asset_requests: list[AssetRequest] = Field(max_length=3)
    visual_relationships: list[VisualRelationship] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def references(self):
        ids = [element.id for element in self.content_elements]
        if len(ids) != len(set(ids)):
            raise ValueError("Element IDs must be unique")
        if set(self.visual_direction.hierarchy) - set(ids):
            raise ValueError("Visual hierarchy references unknown content")
        asset_ids = [asset.id for asset in self.asset_requests]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("Asset request IDs must be unique")
        relationship_ids = [relationship.id for relationship in self.visual_relationships]
        if len(set(relationship_ids)) != len(relationship_ids):
            raise ValueError("Visual relationship IDs must be unique")
        for relationship in self.visual_relationships:
            if {relationship.source_element, relationship.target_element} - set(ids):
                raise ValueError("Visual relationships must refer to saved content elements")
            if (
                relationship.source_element == relationship.target_element
                and relationship.kind != "cycle"
            ):
                raise ValueError("Only a cycle may connect an element to itself")
        return self

    def citation_ids(self):
        refs = [
            ref
            for element in self.content_elements
            for ref in [
                *element.citations,
                *(ref for item in element.items for ref in item.citations),
            ]
        ]
        refs.extend(
            ref for relationship in self.visual_relationships for ref in relationship.citations
        )
        return list(dict.fromkeys(refs))

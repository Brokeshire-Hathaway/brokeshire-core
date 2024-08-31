from typing import (
    ClassVar,
    Generic,
    TypeVar,
)

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from rich import print

from ember_agents.common.agents.entity_extractor import (
    ConfidenceLevel,
    ExtractedEntities,
    flatten_classified_entities,
)

T = TypeVar("T")


"""class ValueWithConfidence(TypedDict):
    value: str
    confidence_percentage: float"""


class InferredEntity(BaseModel, Generic[T]):
    """
    Represents an inferred entity with a confidence level.

    Attributes:
        named_entity (T): The inferred entity.
        confidence_level (ConfidenceLevel): The confidence level of the inference.
        confidence_threshold (ConfidenceLevel): The minimum acceptable confidence level.
    """

    named_entity: T
    confidence_level: ConfidenceLevel = Field(
        ...,
        description="Confidence level of the inference: low, normal, or high",
    )
    confidence_threshold: ConfidenceLevel = Field(
        default="normal", description="Minimum acceptable confidence level"
    )

    CONFIDENCE_ORDER: ClassVar[list[ConfidenceLevel]] = ["low", "normal", "high"]

    @field_validator("confidence_level")
    @classmethod
    def validate_confidence(
        cls, v: ConfidenceLevel, info: ValidationInfo
    ) -> ConfidenceLevel:
        threshold = info.data.get("confidence_threshold", "normal")
        if cls.CONFIDENCE_ORDER.index(v) < cls.CONFIDENCE_ORDER.index(threshold):
            print(f"Confidence '{v}' is below the threshold of '{threshold}'")
            print(cls)
            print(info)
            named_entity = info.data["named_entity"]
            msg = f"Confidence is {v}. Unsure if '{named_entity}' is the correct named entity."
            raise ValueError(msg)
        return v


S = TypeVar("S", bound=BaseModel)


def convert_to_schema(
    schema_class: type[S], data: ExtractedEntities, *, validate: bool = True
) -> S:
    """
    Convert extracted entities to a schema-validated model.

    Args:
        schema_class (type[S]): The schema class to validate against.
        data (ExtractedEntities): The extracted entities data.
        validate (bool, optional): Whether to validate the data. Defaults to True.

    Returns:
        S: An instance of the schema class with validated data.
    """
    data_model = flatten_classified_entities(data)
    return schema_class.model_validate(data_model)

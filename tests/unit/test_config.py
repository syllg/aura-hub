import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_model", "unsupported-model"),
        ("embedding_model", "local-model"),
        ("embedding_dimensions", 384),
    ],
)
def test_locked_model_configuration_rejects_drift(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})

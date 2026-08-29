from pydantic import BaseModel, ValidationError
from fastapi.exceptions import RequestValidationError


def parse_form_model(model: type[BaseModel], raw: str) -> BaseModel:
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors())

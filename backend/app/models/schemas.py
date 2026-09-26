from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class PhotoType(str, Enum):
    FRONT_FULL_BODY = "front_full_body"
    UPPER_BODY = "upper_body"
    LEGS = "legs"
    FEET = "feet"
    FACE = "face"

class ProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name or label for the user profile")

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Updated name for profile")

class ProfilePhotoResponse(BaseModel):
    id: int
    profile_id: int
    photo_type: PhotoType
    created_at: str
    access_url: str = Field(..., description="API endpoint to retrieve the photo stream securely")

class ProfileResponse(BaseModel):
    id: int
    name: str
    created_at: str
    photo_count: int = 0

class ProfileDetailResponse(BaseModel):
    id: int
    name: str
    created_at: str
    photos: List[ProfilePhotoResponse] = []

class ProductCreate(BaseModel):
    source_url: str
    title: Optional[str] = None
    image_urls: List[str] = []
    category: Optional[str] = None
    price: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    source_url: str
    title: Optional[str]
    image_urls: List[str]
    category: Optional[str]
    price: Optional[str]
    detected_at: str

class TryOnRequest(BaseModel):
    profile_id: int = Field(..., description="ID of the user profile")
    garment_image_url: str = Field(..., description="URL or data URI of the garment image")
    product_id: Optional[int] = Field(None, description="Optional associated product ID")
    category: Optional[str] = Field("overall", description="Garment type (upper, lower, overall)")
    photo_type: Optional[PhotoType] = Field(None, description="Specific profile photo type to use")

class ClassifyRequest(BaseModel):
    image_url: str = Field(..., description="Garment image URL or data URI")
    text_hint: Optional[str] = Field(None, description="Optional title or product description hint")


class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    all_scores: Dict[str, float]
    method: str


class TryOnResultResponse(BaseModel):
    id: int
    profile_id: int
    product_id: Optional[int] = None
    category: str
    handler_name: Optional[str] = None
    accuracy_score: Optional[float] = 1.0
    is_low_confidence: bool = False
    accuracy_metrics: Optional[Dict[str, Any]] = None
    created_at: str
    access_url: str


class TryOnStatusResponse(BaseModel):
    space_id: str
    stage: str
    is_ready: bool
    space_url: str



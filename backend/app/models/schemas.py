from enum import Enum
from typing import List, Optional
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

class TryOnResultResponse(BaseModel):
    id: int
    profile_id: int
    product_id: Optional[int]
    category: str
    created_at: str
    access_url: str

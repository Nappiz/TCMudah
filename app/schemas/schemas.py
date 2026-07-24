from __future__ import annotations
from typing import Optional, Literal, Annotated, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing_extensions import Annotated


# ===== Roles =====
Role = Literal["superadmin", "admin", "mentor", "peserta"]

# ===== Auth / Users =====
class RegisterIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    nim: Optional[str] = Field(None, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)  

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)

class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    nim: Optional[str] = None
    role: Role

class UpdateRoleIn(BaseModel):
    role: Role

# ===== Curriculum =====
SemType = Literal[1, 2]

class CurriculumIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=2, max_length=120)
    sem: SemType
    blurb: str = Field(..., min_length=2, max_length=300)

class CurriculumUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    sem: Optional[SemType] = None
    blurb: Optional[str] = Field(None, min_length=2, max_length=300)

class CurriculumOut(CurriculumIn):
    id: str
    created_at: Optional[str] = None

# ===== Testimonials =====
class TestimonialIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    text: str = Field(..., min_length=4, max_length=600)
    visible: bool = True

class TestimonialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    text: Optional[str] = Field(None, min_length=4, max_length=600)
    visible: Optional[bool] = None

class TestimonialOut(TestimonialIn):
    id: str
    created_at: Optional[str] = None

# ===== Batches =====
class BatchIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    is_active: bool = False

class BatchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    is_active: Optional[bool] = None

class BatchOut(BatchIn):
    id: str
    created_at: Optional[str] = None

# ===== Mentor =====
Text160 = Annotated[str, Field(min_length=1, max_length=160)]
Year = Annotated[int, Field(ge=2000, le=2100)]
AchList = Annotated[list[Text160], Field(min_length=1, max_length=5)]

class MentorIn(BaseModel):
    name: Text160 = Field(..., description="Nama mentor")
    angkatan: Year = Field(..., description="Tahun angkatan")
    achievements: AchList = Field(..., description="Prestasi 1..5")
    visible: bool = True

class MentorUpdate(BaseModel):
    name: Optional[Text160] = None
    angkatan: Optional[Year] = None
    achievements: Optional[AchList] = None
    visible: Optional[bool] = None

class MentorOut(MentorIn):
    id: str
    created_at: Optional[str] = None

# ===== Classes (Catalog Kelas) =====
Text150 = Annotated[str, Field(min_length=2, max_length=150)]
Text800 = Annotated[str, Field(min_length=2, max_length=800)]
IdList10 = Annotated[list[str], Field(min_length=1, max_length=10)]
MentorIdList5 = Annotated[list[str], Field(min_length=1, max_length=5)]
NonNegInt = Annotated[int, Field(ge=0)]

class ClassIn(BaseModel):
    title: Text150
    description: Text800
    mentor_ids: MentorIdList5
    curriculum_ids: IdList10
    price: NonNegInt
    visible: bool = True
    batch_id: Optional[str] = None

class ClassUpdate(BaseModel):
    title: Optional[Text150] = None
    description: Optional[Text800] = None
    mentor_ids: Optional[MentorIdList5] = None
    curriculum_ids: Optional[IdList10] = None
    price: Optional[NonNegInt] = None
    visible: Optional[bool] = None
    batch_id: Optional[str] = None

class ClassOut(ClassIn):
    id: str
    created_at: Optional[str] = None

# ===== Checkout / Orders =====
class CheckoutInfoOut(BaseModel):
    bank_name: str
    bank_account: str
    bank_holder: str
    group_link: Optional[str] = None

class OrderItemIn(BaseModel):
    item_id: str
    item_type: Literal["class", "package"] = "class"
    qty: int = Field(..., ge=1, le=99)

class OrderCreateIn(BaseModel):
    items: List[OrderItemIn]
    proof_url: Optional[str] = None
    sender_name: Optional[str] = None
    note: Optional[str] = None

OrderStatus = Literal["pending", "approved", "rejected", "expired"]

class OrderOut(BaseModel):
    id: str
    user_id: str
    items: list[dict]
    total: int
    status: OrderStatus
    proof_url: Optional[str] = None
    sender_name: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None

class AdminOrderOut(OrderOut):
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None

# --- Enrollment ---
class EnrollmentOut(BaseModel):
    id: str
    user_id: str
    class_id: str
    active: bool
    assigned_by: Optional[str] = None
    created_at: Optional[str] = None

class EnrollmentSetIn(BaseModel):
    user_id: str
    class_ids: List[str] 

# --- Materials ---
MaterialType = Literal["video", "ppt"]

class MaterialBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True) 

    class_id: str
    title: str
    url: str
    visible: bool = True
    kind: MaterialType = Field(alias="type")
    batch_id: Optional[str] = None

class MaterialIn(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = None
    url: Optional[str] = None
    visible: Optional[bool] = None
    kind: Optional[MaterialType] = Field(default=None, alias="type")

class MaterialOut(MaterialBase):
    id: str
    created_at: Optional[str] = None

# --- Feedback (anon) ---
Text1000 = Annotated[str, Field(min_length=4, max_length=1000)]
Rating = Annotated[int, Field(ge=1, le=5)]

class FeedbackIn(BaseModel):
    class_id: str
    text: str = Field(..., min_length=4, max_length=1000, alias="message")
    rating: int | None = Field(default=None, ge=1, le=5)

    class Config:
        populate_by_name = True  

class FeedbackOut(BaseModel):
    id: str
    class_id: str
    text: str
    rating: Optional[int] = None
    created_at: Optional[str] = None

class AdminFeedbackOut(FeedbackOut):
    class_title: Optional[str] = None

# --- Shortlinks ---

class ShortlinkBase(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    url: str
    title: str | None = None
    description: str | None = None
    active: bool = True


class ShortlinkIn(ShortlinkBase):
    """Payload create"""
    pass


class ShortlinkUpdate(BaseModel):
    slug: str | None = Field(None, min_length=1, max_length=64)
    url: str | None = None
    title: str | None = None
    description: str | None = None
    active: bool | None = None


class ShortlinkOut(ShortlinkBase):
    id: str
    clicks: int = 0
    created_by: str | None = None
    created_at: str | None = None


class ShortlinkResolveOut(BaseModel):
    url: str

# ===== Packages =====
class PackageIn(BaseModel):
    title: Text150
    description: Text800
    class_ids: list[str] = Field(..., min_length=1) 
    price: NonNegInt
    visible: bool = True
    batch_id: Optional[str] = None

class PackageUpdate(BaseModel):
    title: Optional[Text150] = None
    description: Optional[Text800] = None
    class_ids: Optional[list[str]] = None
    price: Optional[NonNegInt] = None
    visible: Optional[bool] = None
    batch_id: Optional[str] = None

class PackageOut(PackageIn):
    id: str
    created_at: Optional[str] = None

class EnrollmentPackageIn(BaseModel):
    user_id: str
    package_id: str
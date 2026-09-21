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
    items: List[OrderItemIn] = Field(..., min_length=1, max_length=100)
    proof_path: str = Field(..., min_length=3, max_length=512)
    sender_name: Optional[str] = None
    note: Optional[str] = None

class PaymentUploadIntentIn(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(..., ge=1, le=5_242_880)

class PaymentUploadIntentOut(BaseModel):
    signed_url: str
    path: str
    expires_at: str
    max_size_bytes: int

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
    class_ids: List[str] = Field(..., max_length=500)

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
    model_config = ConfigDict(populate_by_name=True)

    class_id: str
    text: str = Field(..., min_length=4, max_length=1000, alias="message")
    rating: int | None = Field(default=None, ge=1, le=5)

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
    slug: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    url: str
    title: str | None = None
    description: str | None = None
    active: bool = True


class ShortlinkIn(ShortlinkBase):
    """Payload create"""
    pass


class ShortlinkUpdate(BaseModel):
    slug: str | None = Field(
        None, min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"
    )
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

# ===== Settings =====
class AppSettingBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str

class AppSettingIn(AppSettingBase):
    pass

class AppSettingOut(AppSettingBase):
    pass

class AppSettingUpdate(BaseModel):
    value: str


# ===== Optimized admin read models =====
class EnrollmentParticipantOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr


class EnrollmentClassOptionOut(BaseModel):
    id: str
    title: str


class EnrollmentPackageOptionOut(BaseModel):
    id: str
    title: str
    class_ids: list[str] = Field(default_factory=list)


class EnrollmentCandidatesOut(BaseModel):
    participants: list[EnrollmentParticipantOut]
    next_cursor: Optional[str] = None
    has_more: bool = False


class EnrollmentBootstrapOut(EnrollmentCandidatesOut):
    classes: list[EnrollmentClassOptionOut]
    packages: list[EnrollmentPackageOptionOut]
    selected_user: Optional[EnrollmentParticipantOut] = None
    active_class_ids: list[str]


class ActiveClassIdsOut(BaseModel):
    class_ids: list[str]


class NotificationsSummaryOut(BaseModel):
    new_orders: int
    new_users: int
    new_feedbacks: int


class DashboardSeriesPointOut(BaseModel):
    key: str
    value: int


class DashboardTopClassOut(BaseModel):
    id: str
    title: str
    count: int
    revenue: int


class DashboardStatsOut(BaseModel):
    total_users: int
    superadmin: int
    admin: int
    mentor: int
    peserta: int
    new_users_30d: int
    total_curriculum: int
    total_testimonials: int
    visible_testimonials: int
    hidden_testimonials: int
    total_mentors: int
    visible_mentors: int
    total_classes: int
    visible_classes: int
    class_per_mentor: float
    total_orders: int
    pending_orders: int
    approved_orders: int
    rejected_orders: int
    expired_orders: int
    revenue_approved: int
    revenue_30d: int
    participants_active: int
    aov: float
    approval_rate: int
    order_series: list[DashboardSeriesPointOut]
    revenue_series: list[DashboardSeriesPointOut]


class DashboardPeriodOut(BaseModel):
    total_orders: int
    pending_orders: int
    approved_orders: int
    rejected_orders: int
    expired_orders: int
    revenue_approved: int
    aov: float
    approval_rate: int
    class_revenue: int
    package_revenue: int
    top_classes: list[DashboardTopClassOut]


class DashboardOrderPreviewOut(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None
    sender_name: Optional[str] = None
    total: int
    status: OrderStatus
    created_at: Optional[str] = None


class DashboardOverviewOut(BaseModel):
    me: UserOut
    stats: DashboardStatsOut
    period: DashboardPeriodOut
    pending_latest: list[DashboardOrderPreviewOut]
    recent_orders: list[DashboardOrderPreviewOut]


class PaginatedFeedbackOut(BaseModel):
    total: int
    data: list[AdminFeedbackOut]


class PaginatedShortlinksOut(BaseModel):
    total: int
    data: list[ShortlinkOut]


class CatalogOut(BaseModel):
    active_batch_id: Optional[str] = None
    mentors: list[MentorOut]
    curriculum: list[CurriculumOut]
    classes: list[ClassOut]
    packages: list[PackageOut]

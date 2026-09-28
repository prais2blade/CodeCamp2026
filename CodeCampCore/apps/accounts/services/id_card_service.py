import os
import hashlib
import random
from io import BytesIO
from datetime import date
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
import qrcode


ID_CARD_SIZE = (
    98.5 * mm,
    67 * mm,
)
BULK_ID_CARD_PAGE_SIZE = landscape(A4)
BULK_ID_CARD_COLUMNS = 3
BULK_ID_CARD_ROWS = 3
ID_CARDS_PER_BULK_PAGE = BULK_ID_CARD_COLUMNS * BULK_ID_CARD_ROWS

CARD_WIDTH = ID_CARD_SIZE[0]
CARD_HEIGHT = ID_CARD_SIZE[1]

CARD_MARGIN = 4
CARD_X = CARD_MARGIN
CARD_Y = CARD_MARGIN
CARD_W = CARD_WIDTH - (CARD_MARGIN * 2)
CARD_H = CARD_HEIGHT - (CARD_MARGIN * 2)

DEEP_PURPLE = colors.HexColor("#241045")
ROYAL_PURPLE = colors.HexColor("#56207F")
VIOLET = colors.HexColor("#7B2DB8")
HOT_PINK = colors.HexColor("#F12BBE")
SOFT_PINK = colors.HexColor("#FF7BD8")
WHITE = colors.white
MUTED = colors.HexColor("#E7DAF6")
GREEN = colors.HexColor("#2E9D78")
SLATE = colors.HexColor("#657083")

DEFAULT_CODECAMP_LOGO_PATH = Path(settings.BASE_DIR) / "static" / "images" / "codecamp-logo.png"


def get_existing_file_path(field_file):
    """Safely extracts the absolute path of a Django FileField/ImageField if it exists."""
    if not field_file:
        return None
    if isinstance(field_file, str) and os.path.exists(field_file):
        return field_file
    if hasattr(field_file, "path"):
        try:
            if os.path.exists(field_file.path):
                return field_file.path
        except Exception:
            pass
    if hasattr(field_file, "name") and hasattr(field_file, "storage"):
        try:
            if field_file.storage.exists(field_file.name):
                return field_file.path
        except Exception:
            pass
    return None


class StudentAdapter:
    """
    Adapts a CodeCampCore Profile, User, or dictionary to the interface expected
    by the Attendance System ID Card generator.
    """
    def __init__(self, target):
        self.target = target
        # Handle User instance passed directly
        if hasattr(target, 'profile'):
            self.profile = target.profile
            self.user = target
        else:
            self.profile = target
            self.user = getattr(target, 'user', None)

    @property
    def student_id(self):
        if hasattr(self.profile, 'external_attendance_id') and self.profile.external_attendance_id:
            return str(self.profile.external_attendance_id).strip()
        if self.user and hasattr(self.user, 'id'):
            return f"CDCP-{self.user.id:06d}"
        return "CDCP-000000"

    @property
    def first_name(self):
        if self.user and self.user.first_name:
            return self.user.first_name.strip()
        return ""

    @property
    def last_name(self):
        if self.user and self.user.last_name:
            return self.user.last_name.strip()
        return ""

    @property
    def full_name(self):
        if self.user:
            name = f"{self.user.first_name} {self.user.last_name}".strip()
            if name:
                return name
            return self.user.username
        return getattr(self.profile, 'full_name', "STUDENT")

    @property
    def class_name(self):
        if hasattr(self.profile, 'course') and self.profile.course:
            return self.profile.course.name
        if hasattr(self.profile, 'batch') and self.profile.batch:
            return self.profile.batch.name
        return "Software Engineering"

    @property
    def photo(self):
        if hasattr(self.profile, 'avatar') and self.profile.avatar:
            return self.profile.avatar
        photo_attr = getattr(self.profile, 'photo', None)
        if photo_attr:
            return photo_attr
        sid = getattr(self, 'student_id', None)
        if sid:
            try:
                from apps.accounts.services.attendance_sync_service import AttendanceSyncService
                return AttendanceSyncService.find_student_photo_file(
                    student_id=sid,
                    first_name=self.first_name,
                    last_name=self.last_name,
                )
            except Exception:
                pass
        return None

    @property
    def qr_code(self):
        return getattr(self.profile, 'qr_code', None)

    @property
    def is_active(self):
        if hasattr(self.profile, 'student_status'):
            return self.profile.student_status == 'active'
        if self.user and hasattr(self.user, 'is_active'):
            return self.user.is_active
        return True


def normalize_student(student_or_profile):
    """Ensures the object has the required properties (student_id, full_name, etc.)."""
    if hasattr(student_or_profile, 'student_id') and hasattr(student_or_profile, 'full_name') and not hasattr(student_or_profile, 'user'):
        return student_or_profile
    return StudentAdapter(student_or_profile)


def get_id_card_settings():
    """Retrieves tenant or system branding settings."""
    try:
        from apps.tenants.models import Tenant
        from apps.tenants.middleware import get_current_tenant
        tenant = get_current_tenant() or Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()
        return tenant
    except Exception:
        return None


def get_bulk_id_card_position(index):
    slot_index = index % ID_CARDS_PER_BULK_PAGE
    column = slot_index % BULK_ID_CARD_COLUMNS
    row = (BULK_ID_CARD_ROWS - 1) - (slot_index // BULK_ID_CARD_COLUMNS)

    return (
        column * ID_CARD_SIZE[0],
        row * ID_CARD_SIZE[1],
    )


def _organization_name(system_settings):
    if system_settings and hasattr(system_settings, "name") and system_settings.name:
        return system_settings.name.strip()
    if system_settings and hasattr(system_settings, "organization_name") and system_settings.organization_name:
        return system_settings.organization_name.strip()

    return "CodeCamp Innovation Hub"


def draw_student_id_card(
    pdf,
    student,
    system_settings=None,
    x=0,
    y=0,
    width=None,
    height=None,
):
    """
    Draw one premium student ID card in a CR100 98.5mm x 67mm landscape slot.
    Identical rendering engine to the Attendance System ID Card Generator with dynamic text-wrap.
    """
    student = normalize_student(student)
    system_settings = system_settings or get_id_card_settings()
    organization_name = _organization_name(system_settings)
    width = width or ID_CARD_SIZE[0]
    height = height or ID_CARD_SIZE[1]

    pdf.saveState()

    try:
        pdf.translate(x, y)
        pdf.scale(
            width / CARD_WIDTH,
            height / CARD_HEIGHT,
        )

        _draw_background(pdf, student)
        _draw_brand(pdf, organization_name, system_settings)
        _draw_photo(pdf, student)
        _draw_student_details(pdf, student)
        _draw_qr_code(pdf, student)
        _draw_status(pdf, student)
        _draw_footer(pdf, organization_name)
    finally:
        pdf.restoreState()


def _draw_background(pdf, student):
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, CARD_WIDTH, CARD_HEIGHT, fill=1, stroke=0)

    pdf.setFillColor(DEEP_PURPLE)
    pdf.roundRect(CARD_X, CARD_Y, CARD_W, CARD_H, 9, fill=1, stroke=0)

    _draw_gradient_band(
        pdf,
        CARD_Y + 9,
        CARD_Y + CARD_H - 6,
        ROYAL_PURPLE,
        DEEP_PURPLE,
        28,
    )

    _draw_glow(pdf, CARD_X + CARD_W * 0.64, CARD_Y + CARD_H * 0.58, 78, VIOLET)
    _draw_glow(pdf, CARD_X + CARD_W * 0.78, CARD_Y + CARD_H * 0.24, 42, HOT_PINK)
    _draw_speckles(pdf, student)

    _draw_wave(
        pdf,
        y=CARD_Y + CARD_H * 0.72,
        height=16,
        stroke_color=SOFT_PINK,
        fill_color=colors.Color(0.92, 0.12, 0.72, alpha=0.15),
        line_width=1.8,
    )
    _draw_wave(
        pdf,
        y=CARD_Y + CARD_H * 0.22,
        height=19,
        stroke_color=HOT_PINK,
        fill_color=colors.Color(0.89, 0.12, 0.76, alpha=0.22),
        line_width=2.2,
    )


def _draw_gradient_band(pdf, bottom, top, start_color, end_color, steps):
    band_height = (top - bottom) / steps

    for step in range(steps):
        ratio = step / max(steps - 1, 1)
        color = colors.Color(
            start_color.red + ((end_color.red - start_color.red) * ratio),
            start_color.green + ((end_color.green - start_color.green) * ratio),
            start_color.blue + ((end_color.blue - start_color.blue) * ratio),
        )

        pdf.setFillColor(color)
        pdf.rect(
            CARD_X,
            bottom + (step * band_height),
            CARD_W,
            band_height + 1,
            fill=1,
            stroke=0,
        )


def _draw_glow(pdf, cx, cy, radius, color):
    for step in range(10, 0, -1):
        factor = step / 10
        pdf.setFillColor(
            colors.Color(
                color.red,
                color.green,
                color.blue,
                alpha=0.035 * factor,
            )
        )
        pdf.circle(cx, cy, radius * factor, fill=1, stroke=0)


def _draw_speckles(pdf, student):
    seed = hashlib.sha256(str(student.student_id).encode("utf-8")).hexdigest()
    rng = random.Random(seed)

    for _ in range(90):
        x = rng.uniform(CARD_X + 8, CARD_X + CARD_W - 8)
        y = rng.uniform(CARD_Y + 12, CARD_Y + CARD_H - 24)
        radius = rng.uniform(0.12, 0.38)
        alpha = rng.uniform(0.08, 0.26)
        pdf.setFillColor(colors.Color(1, 1, 1, alpha=alpha))
        pdf.circle(x, y, radius, fill=1, stroke=0)


def _draw_wave(pdf, y, height, stroke_color, fill_color, line_width):
    path = pdf.beginPath()
    path.moveTo(CARD_X, y)
    path.curveTo(
        CARD_X + CARD_W * 0.24,
        y - height,
        CARD_X + CARD_W * 0.47,
        y + height * 0.85,
        CARD_X + CARD_W,
        y + height * 0.18,
    )
    path.lineTo(CARD_X + CARD_W, y - 5)
    path.curveTo(
        CARD_X + CARD_W * 0.68,
        y - height * 0.7,
        CARD_X + CARD_W * 0.42,
        y + height * 0.15,
        CARD_X,
        y - height * 0.45,
    )
    path.close()

    pdf.setFillColor(fill_color)
    pdf.drawPath(path, fill=1, stroke=0)

    line = pdf.beginPath()
    line.moveTo(CARD_X, y)
    line.curveTo(
        CARD_X + CARD_W * 0.24,
        y - height,
        CARD_X + CARD_W * 0.47,
        y + height * 0.85,
        CARD_X + CARD_W,
        y + height * 0.18,
    )
    pdf.setStrokeColor(stroke_color)
    pdf.setLineWidth(line_width)
    pdf.drawPath(line, fill=0, stroke=1)


def _draw_brand(pdf, organization_name, system_settings):
    logo_path, use_default_logo = _brand_logo_path(system_settings)
    logo_x = CARD_X + 13
    logo_y = CARD_Y + CARD_H - 35
    logo_size = 27

    if logo_path:
        if use_default_logo:
            _draw_default_codecamp_logo(pdf, logo_path, logo_x, logo_y, logo_size)
        else:
            pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.88))
            pdf.roundRect(logo_x, logo_y, logo_size, logo_size, 5, fill=1, stroke=0)
            _draw_image_fit(
                pdf,
                logo_path,
                logo_x + 2,
                logo_y + 2,
                logo_size - 4,
                logo_size - 4,
            )
    else:
        _draw_fallback_logo(pdf, logo_x, logo_y, logo_size)

    text_x = logo_x + logo_size + 8
    text_y = logo_y + 17

    pdf.setFillColor(WHITE)
    _draw_fit_text(
        pdf,
        organization_name.upper(),
        text_x,
        text_y,
        CARD_X + CARD_W - text_x - 15,
        "Helvetica-Bold",
        13,
        7.5,
    )

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(text_x, text_y - 11, "STUDENT IDENTIFICATION CARD")


def _brand_logo_path(system_settings):
    uploaded_logo_path = None
    if system_settings and hasattr(system_settings, 'logo'):
        uploaded_logo_path = get_existing_file_path(system_settings.logo)

    if uploaded_logo_path:
        return uploaded_logo_path, False

    if DEFAULT_CODECAMP_LOGO_PATH.exists():
        return str(DEFAULT_CODECAMP_LOGO_PATH), True

    return None, False


def _draw_default_codecamp_logo(pdf, image_path, x, y, size):
    image = _codecamp_mark_reader(image_path)

    if not image:
        _draw_fallback_logo(pdf, x, y, size)
        return

    pdf.setFillColor(colors.Color(0.38, 0.14, 0.72, alpha=0.22))
    pdf.circle(x + (size / 2), y + (size / 2), size * 0.62, fill=1, stroke=0)
    pdf.drawImage(
        image,
        x - 1,
        y - 1,
        width=size + 2,
        height=size + 2,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _codecamp_mark_reader(image_path):
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            crop_box = (
                int(width * 0.23),
                int(height * 0.04),
                int(width * 0.77),
                int(height * 0.58),
            )
            image = image.crop(crop_box)
            return ImageReader(image.copy())
    except (OSError, ValueError):
        return None


def _draw_fallback_logo(pdf, x, y, size):
    pdf.setFillColor(colors.Color(0.97, 0.25, 0.74, alpha=0.2))
    pdf.roundRect(x, y, size, size, 7, fill=1, stroke=0)

    pdf.setStrokeColor(SOFT_PINK)
    pdf.setLineCap(1)
    pdf.setLineWidth(3)
    pdf.arc(x + 3, y + 5, x + size - 3, y + size - 3, 88, 250)
    pdf.setStrokeColor(HOT_PINK)
    pdf.arc(x + 7, y + 7, x + size + 1, y + size - 2, 92, 228)

    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(x + (size / 2), y + 7.5, "C")


def _draw_photo(pdf, student):
    cx = CARD_X + CARD_W * 0.25
    cy = CARD_Y + CARD_H * 0.50
    radius = 39
    photo_path = get_existing_file_path(student.photo)

    pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.23))
    pdf.circle(cx + 2, cy - 2, radius + 3, fill=1, stroke=0)

    pdf.setFillColor(WHITE)
    pdf.circle(cx, cy, radius + 3, fill=1, stroke=0)

    if photo_path:
        success = _draw_circular_image(pdf, photo_path, cx, cy, radius)
        if not success:
            _draw_initials_placeholder(pdf, student, cx, cy, radius)
    else:
        _draw_initials_placeholder(pdf, student, cx, cy, radius)


def _draw_circular_image(pdf, image_path, cx, cy, radius):
    image = _square_image_reader(image_path)

    if not image:
        return False

    pdf.saveState()
    clip = pdf.beginPath()
    clip.circle(cx, cy, radius)
    pdf.clipPath(clip, stroke=0, fill=0)
    pdf.drawImage(
        image,
        cx - radius,
        cy - radius,
        width=radius * 2,
        height=radius * 2,
        mask="auto",
    )
    pdf.restoreState()
    return True


def _square_image_reader(image_path):
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            image = image.crop((left, top, left + side, top + side))
            return ImageReader(image.copy())
    except (OSError, ValueError):
        return None


def _draw_initials_placeholder(pdf, student, cx, cy, radius):
    first = getattr(student, 'first_name', '')
    last = getattr(student, 'last_name', '')
    initials = "".join(
        part[:1]
        for part in [first, last]
        if part
    ).upper()

    if not initials:
        full = getattr(student, 'full_name', '')
        initials = "".join(part[:1] for part in full.split() if part).upper()

    initials = initials[:2] or "ST"

    pdf.setFillColor(colors.HexColor("#F2E9FF"))
    pdf.circle(cx, cy, radius, fill=1, stroke=0)
    pdf.setFillColor(VIOLET)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(cx, cy - 7, initials)


def _student_class_label(student):
    teaching_class = getattr(student, "teaching_class", None)
    if teaching_class:
        return getattr(teaching_class, 'name', str(teaching_class))

    class_name = getattr(student, "class_name", None)
    if class_name:
        return class_name

    return "Student"


def _draw_student_details(pdf, student):
    """
    Renders student full name and course/class label using dynamic multi-line wrapping
    and font auto-scaling to prevent any text clipping.
    """
    x = CARD_X + CARD_W * 0.43
    y = CARD_Y + CARD_H * 0.63
    qr_x, _, _, _ = _qr_box_geometry()
    max_width = qr_x - x - 8
    full_name = student.full_name.upper().strip()

    # Dynamic text-wrap: scales font size down and wraps up to 5 lines
    lines, font_size = _fit_wrapped_text(
        full_name,
        "Helvetica-Bold",
        max_width,
        max_lines=5,
        max_size=13.8,
        min_size=5.8,
    )

    pdf.setFillColor(WHITE)
    line_gap = max(font_size * 0.96, 6.7)
    pdf.setFont("Helvetica-Bold", font_size)

    for index, line in enumerate(lines):
        pdf.drawString(x, y - (index * line_gap), line)

    after_name_y = y - (len(lines) * line_gap) - 3

    # Dynamic course text-wrap: wraps up to 3 lines
    class_lines, class_font_size = _fit_wrapped_text(
        _student_class_label(student).upper(),
        "Helvetica-Bold",
        max_width,
        max_lines=3,
        max_size=7.9,
        min_size=4.8,
    )
    class_line_gap = max(class_font_size * 1.05, 5.4)

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", class_font_size)

    for index, line in enumerate(class_lines):
        pdf.drawString(x, after_name_y - (index * class_line_gap), line)

    after_class_y = after_name_y - (len(class_lines) * class_line_gap) - 7

    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 8.2)
    pdf.drawString(x, after_class_y, "ID:")
    _draw_fit_text(
        pdf,
        student.student_id,
        x + 16,
        after_class_y,
        max_width - 16,
        "Helvetica-Bold",
        10,
        7,
    )


def _draw_qr_code(pdf, student):
    box_x, box_y, box_size, _ = _qr_box_geometry()

    pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.96))
    pdf.roundRect(box_x, box_y, box_size, box_size, 4, fill=1, stroke=0)

    # 1. Try existing file if student has a QR image
    qr_code_path = get_existing_file_path(getattr(student, 'qr_code', None))
    if qr_code_path:
        try:
            pdf.drawImage(
                qr_code_path,
                box_x + 4,
                box_y + 4,
                width=box_size - 8,
                height=box_size - 8,
                mask="auto",
            )
            return
        except Exception:
            pass

    # 2. Dynamic high-resolution QR generation via qrcode
    try:
        student_id = getattr(student, 'student_id', '') or 'STUDENT'
        full_name = getattr(student, 'full_name', '') or ''
        data = f"CODECAMP-STUDENT:{student_id}:{full_name}"

        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        reader = ImageReader(buf)

        pdf.drawImage(
            reader,
            box_x + 4,
            box_y + 4,
            width=box_size - 8,
            height=box_size - 8,
            mask="auto",
        )
        return
    except Exception:
        pass

    # 3. Fallback text
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 6)
    pdf.drawCentredString(
        box_x + (box_size / 2),
        box_y + (box_size / 2),
        "QR unavailable",
    )


def _draw_status(pdf, student):
    valid_until = _valid_until()
    box_x, _, box_size, _ = _qr_box_geometry()
    y = CARD_Y + 35

    pdf.setFillColor(WHITE)
    _draw_fit_centered_text(
        pdf,
        f"VALID UNTIL: {valid_until}",
        box_x + (box_size / 2),
        y + 18,
        70,
        "Helvetica-Bold",
        6.4,
        4.8,
    )

    active = getattr(student, "is_active", True)
    badge_color = GREEN if active else SLATE
    badge_text = "ACTIVE" if active else "INACTIVE"
    badge_w = 52
    badge_h = 13
    badge_x = box_x + ((box_size - badge_w) / 2)
    badge_y = y

    pdf.setFillColor(badge_color)
    pdf.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 8.4)
    pdf.drawCentredString(badge_x + (badge_w / 2), badge_y + 3.4, badge_text)


def _qr_box_geometry():
    box_size = 58
    box_x = CARD_X + CARD_W - box_size - 15
    box_y = CARD_Y + 75

    return box_x, box_y, box_size, box_size


def _valid_until():
    today = timezone.localdate()
    if not isinstance(today, date):
        today = date.today()
    return date(today.year + 1, 12, 31).strftime("%b %d, %Y").upper()


def _draw_footer(pdf, organization_name):
    text = f"Property of {organization_name}"
    pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.86))
    _draw_fit_text(
        pdf,
        text,
        CARD_X + 13,
        CARD_Y + 7,
        CARD_W - 26,
        "Helvetica",
        6.8,
        4.8,
    )


def _draw_image_fit(pdf, image_path, x, y, width, height):
    try:
        image = ImageReader(image_path)
    except (OSError, ValueError):
        return

    pdf.drawImage(
        image,
        x,
        y,
        width=width,
        height=height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _draw_fit_text(pdf, text, x, y, max_width, font_name, max_size, min_size):
    size = max_size

    while size > min_size and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 0.5

    pdf.setFont(font_name, size)
    pdf.drawString(x, y, text)


def _draw_fit_centered_text(
    pdf,
    text,
    center_x,
    y,
    max_width,
    font_name,
    max_size,
    min_size,
):
    size = max_size

    while size > min_size and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 0.5

    pdf.setFont(font_name, size)
    pdf.drawCentredString(center_x, y, text)


def _fit_wrapped_text(text, font_name, max_width, max_lines, max_size, min_size):
    """
    Fits text within max_width and max_lines by iteratively reducing font size.
    If even min_size overflows, splits long words to guarantee no clipping.
    """
    size = max_size

    while size >= min_size:
        lines = _wrap_text(
            text,
            font_name,
            size,
            max_width,
            split_long_words=False,
        )

        if len(lines) <= max_lines and _lines_fit(lines, font_name, size, max_width):
            return lines, size

        size -= 0.5

    return _wrap_text(text, font_name, min_size, max_width, split_long_words=True), min_size


def _wrap_text(text, font_name, font_size, max_width, split_long_words=True):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        word_parts = (
            _split_word_to_width(word, font_name, font_size, max_width)
            if split_long_words
            else [word]
        )

        for part in word_parts:
            candidate = f"{current} {part}".strip()

            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)

            current = part

    if current:
        lines.append(current)

    return lines or [text]


def _lines_fit(lines, font_name, font_size, max_width):
    return all(
        pdfmetrics.stringWidth(line, font_name, font_size) <= max_width
        for line in lines
    )


def _split_word_to_width(word, font_name, font_size, max_width):
    if pdfmetrics.stringWidth(word, font_name, font_size) <= max_width:
        return [word]

    parts = []
    current = ""

    for char in word:
        candidate = f"{current}{char}"

        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue

        if current:
            parts.append(current)

        current = char

    if current:
        parts.append(current)

    return parts


class IDCardService:
    """
    High-level service class providing single and bulk ID card PDF generation
    for CodeCampCore, using the exact text-wrapping ID generator engine from Attendance System.
    """

    @classmethod
    def generate_student_id_card_pdf(cls, profile_or_student):
        """Generates a PDF buffer containing a single student's official ID Card."""
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=ID_CARD_SIZE)

        draw_student_id_card(pdf, profile_or_student)

        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        return buffer

    @classmethod
    def generate_bulk_id_cards_pdf(cls, profiles_or_students):
        """
        Generates a PDF buffer containing multiple ID cards formatted 9 per landscape A4 sheet (3x3 grid).
        """
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=BULK_ID_CARD_PAGE_SIZE)
        id_card_settings = get_id_card_settings()

        for index, student in enumerate(profiles_or_students):
            if index and index % ID_CARDS_PER_BULK_PAGE == 0:
                pdf.showPage()

            pdf.setPageSize(BULK_ID_CARD_PAGE_SIZE)
            x, y = get_bulk_id_card_position(index)
            draw_student_id_card(
                pdf,
                student,
                id_card_settings,
                x=x,
                y=y,
            )

        pdf.save()
        buffer.seek(0)
        return buffer

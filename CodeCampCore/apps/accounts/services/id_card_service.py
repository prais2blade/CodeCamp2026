import os
import hashlib
import random
from io import BytesIO
from datetime import date

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import qrcode

ID_CARD_SIZE = (98.5 * mm, 67 * mm)
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
GOLD = colors.HexColor("#F59E0B")


class IDCardService:
    """
    Renders and streams high-resolution, print-ready official CodeCamp Student ID Cards (PDF).
    CR100 Landscape (98.5mm x 67mm) format with branding, circular photo, student details,
    cohort, and dynamic verification QR code.
    """

    @classmethod
    def generate_student_id_card_pdf(cls, profile):
        """Generates a PDF buffer containing the student's official ID Card."""
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=ID_CARD_SIZE)

        cls._draw_background(pdf, profile)
        cls._draw_brand(pdf)
        cls._draw_photo(pdf, profile)
        cls._draw_student_details(pdf, profile)
        cls._draw_qr_code(pdf, profile)
        cls._draw_status(pdf, profile)
        cls._draw_footer(pdf)

        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        return buffer

    @classmethod
    def _draw_background(cls, pdf, profile):
        # White background outer border
        pdf.setFillColor(colors.white)
        pdf.rect(0, 0, CARD_WIDTH, CARD_HEIGHT, fill=1, stroke=0)

        # Deep purple card base
        pdf.setFillColor(DEEP_PURPLE)
        pdf.roundRect(CARD_X, CARD_Y, CARD_W, CARD_H, 9, fill=1, stroke=0)

        # Gradient band
        cls._draw_gradient_band(
            pdf,
            CARD_Y + 9,
            CARD_Y + CARD_H - 6,
            ROYAL_PURPLE,
            DEEP_PURPLE,
            28
        )

        # Ambient glows
        cls._draw_glow(pdf, CARD_X + CARD_W * 0.64, CARD_Y + CARD_H * 0.58, 78, VIOLET)
        cls._draw_glow(pdf, CARD_X + CARD_W * 0.78, CARD_Y + CARD_H * 0.24, 42, HOT_PINK)

        # Waves
        cls._draw_wave(
            pdf,
            y=CARD_Y + CARD_H * 0.72,
            height=16,
            stroke_color=SOFT_PINK,
            fill_color=colors.Color(0.92, 0.12, 0.72, alpha=0.15),
            line_width=1.8,
        )
        cls._draw_wave(
            pdf,
            y=CARD_Y + CARD_H * 0.22,
            height=19,
            stroke_color=HOT_PINK,
            fill_color=colors.Color(0.89, 0.12, 0.76, alpha=0.22),
            line_width=2.2,
        )

    @classmethod
    def _draw_gradient_band(cls, pdf, bottom, top, start_color, end_color, steps):
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

    @classmethod
    def _draw_glow(cls, pdf, cx, cy, radius, color):
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

    @classmethod
    def _draw_wave(cls, pdf, y, height, stroke_color, fill_color, line_width):
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
        pdf.setStrokeColor(stroke_color)
        pdf.setLineWidth(line_width)
        pdf.drawPath(path, fill=1, stroke=1)

    @classmethod
    def _draw_brand(cls, pdf):
        # Header Brand Text
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(CARD_X + 14, CARD_Y + CARD_H - 17, "CODECAMP INNOVATION HUB")

        pdf.setFillColor(SOFT_PINK)
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawString(CARD_X + 14, CARD_Y + CARD_H - 24, "OFFICIAL STUDENT IDENTITY CARD")

    @classmethod
    def _draw_photo(cls, pdf, profile):
        cx = CARD_X + CARD_W * 0.22
        cy = CARD_Y + CARD_H * 0.48
        radius = 36

        # Outer glow ring
        pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.25))
        pdf.circle(cx + 2, cy - 2, radius + 3, fill=1, stroke=0)

        pdf.setFillColor(WHITE)
        pdf.circle(cx, cy, radius + 3, fill=1, stroke=0)

        # If custom avatar uploaded
        photo_path = None
        if profile.has_custom_avatar:
            try:
                if os.path.exists(profile.avatar.path):
                    photo_path = profile.avatar.path
            except Exception:
                pass

        if photo_path:
            try:
                img = Image.open(photo_path).convert("RGBA")
                size = min(img.size)
                left = (img.size[0] - size) // 2
                top = (img.size[1] - size) // 2
                cropped = img.crop((left, top, left + size, top + size))
                resized = cropped.resize((250, 250), Image.Resampling.LANCZOS)

                img_buffer = BytesIO()
                resized.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                reader = ImageReader(img_buffer)

                pdf.saveState()
                clip = pdf.beginPath()
                clip.circle(cx, cy, radius)
                pdf.clipPath(clip, stroke=0, fill=0)
                pdf.drawImage(reader, cx - radius, cy - radius, width=radius * 2, height=radius * 2, mask='auto')
                pdf.restoreState()
                return
            except Exception:
                pass

        # Fallback Initials Avatar
        pdf.setFillColor(colors.HexColor("#4F46E5"))
        pdf.circle(cx, cy, radius, fill=1, stroke=0)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 26)
        initials = (profile.user.first_name[:1] or profile.user.username[:1]).upper()
        pdf.drawCentredString(cx, cy - 9, initials)

    @classmethod
    def _draw_student_details(cls, pdf, profile):
        x = CARD_X + CARD_W * 0.40
        y = CARD_Y + CARD_H * 0.65
        user = profile.user

        full_name = (user.get_full_name() or user.username).upper()
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 11.5)
        # Handle long names
        if len(full_name) > 22:
            pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(x, y, full_name)

        # Track / Course
        course_name = (profile.course.name if profile.course else "Innovation Track").upper()
        pdf.setFillColor(SOFT_PINK)
        pdf.setFont("Helvetica-Bold", 7.5)
        if len(course_name) > 28:
            pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawString(x, y - 11, course_name)

        # Batch / Cohort
        batch_name = (profile.batch.name if profile.batch else "Standard Cohort")
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.8)
        pdf.drawString(x, y - 20, f"Cohort: {batch_name}")

        # Official Student ID
        student_id = profile.external_attendance_id or f"CDCP-{user.id:06d}"
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.drawString(x, y - 34, student_id)

    @classmethod
    def _draw_qr_code(cls, pdf, profile):
        # QR Box positioning (bottom right)
        size = 46
        qx = CARD_X + CARD_W - size - 8
        qy = CARD_Y + 12

        # White background backing
        pdf.setFillColor(WHITE)
        pdf.roundRect(qx - 2, qy - 2, size + 4, size + 4, 4, fill=1, stroke=0)

        try:
            student_id = profile.external_attendance_id or f"CDCP-{profile.user.id:06d}"
            verification_data = f"CODECAMP-STUDENT:{student_id}:{profile.user.username}"

            qr = qrcode.QRCode(version=1, box_size=3, border=0)
            qr.add_data(verification_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            qr_buffer = BytesIO()
            img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            reader = ImageReader(qr_buffer)

            pdf.drawImage(reader, qx, qy, width=size, height=size)
        except Exception:
            pdf.setFillColor(colors.lightgrey)
            pdf.rect(qx, qy, size, size, fill=1, stroke=0)

    @classmethod
    def _draw_status(cls, pdf, profile):
        # Active Status Pill
        sx = CARD_X + CARD_W * 0.40
        sy = CARD_Y + 16
        is_active = profile.student_status == 'active'

        bg_color = GREEN if is_active else colors.HexColor("#EF4444")
        pdf.setFillColor(bg_color)
        pdf.roundRect(sx, sy, 58, 12, 6, fill=1, stroke=0)

        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 6.5)
        status_text = "ACTIVE" if is_active else "INACTIVE"
        pdf.drawCentredString(sx + 29, sy + 3.5, status_text)

    @classmethod
    def _draw_footer(cls, pdf):
        pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.6))
        pdf.setFont("Helvetica", 5.2)
        pdf.drawString(CARD_X + 12, CARD_Y + 7, "Valid across all CodeCamp Hubs & Smart Attendance Terminals. codecamp.com.ng")

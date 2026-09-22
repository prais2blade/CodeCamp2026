def qr_code_file_exists(student):
    if not student.qr_code or not student.qr_code.name:
        return False

    try:
        return student.qr_code.storage.exists(student.qr_code.name)
    except (OSError, ValueError):
        return False


def regenerate_student_qr_code(student):
    old_name = student.qr_code.name if student.qr_code else ""

    if old_name:
        try:
            if student.qr_code.storage.exists(old_name):
                student.qr_code.storage.delete(old_name)
        except (OSError, ValueError):
            pass

    student.generate_qr_code()
    student.save(
        update_fields=[
            "qr_code",
        ]
    )

    return student


def ensure_student_qr_code(student):
    if qr_code_file_exists(student):
        return False

    regenerate_student_qr_code(student)
    return True


def get_existing_file_path(field_file):
    if not field_file or not field_file.name:
        return None

    try:
        if field_file.storage.exists(field_file.name):
            return field_file.path
    except (NotImplementedError, OSError, ValueError):
        return None

    return None

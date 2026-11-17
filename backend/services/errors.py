class ApiError(Exception):
    """Lỗi nghiệp vụ -> HTTP. Body: {"error": {"code","message"}}"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.headers: dict | None = None


def not_found(what: str, key) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"Không tìm thấy {what}: {key}")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def bad_request(message: str, code: str = "BAD_REQUEST") -> ApiError:
    return ApiError(400, code, message)

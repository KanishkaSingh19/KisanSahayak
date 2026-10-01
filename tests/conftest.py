"""Tests run on the committed advisories only: PAU's Package of Practices chapters are not in the
repository (copyrighted), so a developer's local copy must not change test results, and tests must
never download them. Tests that need PAU text build a small fake chapter themselves."""

from app.config import settings

settings.USE_PAU_KB = False
settings.PAU_AUTO_BUILD = False

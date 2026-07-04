from enum import Enum

class AppMode(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"
    ENTERPRISE = "enterprise"

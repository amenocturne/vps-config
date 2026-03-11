class VpsError(Exception):
    pass


class SecretsError(VpsError):
    pass


class ConfigError(VpsError):
    pass


class AnsibleError(VpsError):
    pass


class ApiError(VpsError):
    pass

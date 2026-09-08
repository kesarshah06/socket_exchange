import resource
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
print(f"Current limits: Soft={soft}, Hard={hard}")

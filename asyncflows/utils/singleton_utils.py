class SingletonContext:
    def __init__(self):
        self.entry_count = 0

    def enter(self):
        raise NotImplementedError

    def exit(self):
        raise NotImplementedError

    def __enter__(self):
        self.entry_count += 1
        if self.entry_count > 1:
            return
        self.enter()

    def __exit__(self, *args):
        self.entry_count -= 1
        if self.entry_count > 0:
            return
        self.exit()

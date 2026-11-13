class Session:
    """a SHARED DES. session_id is the stored id as a string."""

    def __init__(self, session_id, name, owner, public=True, created=None):
        self.id = session_id
        self.name = name
        self.owner = owner
        self.public = public
        self.created = created

    def is_owned_by(self, username):
        return self.owner == username

    def is_visible_to(self, username):
        """private sessions available only to the person who created them."""
        return self.public or self.owner == username
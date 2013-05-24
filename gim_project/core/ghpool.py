from github import GitHub, ApiError, ApiAuthError, ApiNotFoundError


class Connection(GitHub):
    """
    A subclass of the default GitHub object to handle a pool of connections,
    one for each username
    """
    pool = {}
    ApiError = ApiError
    ApiAuthError = ApiAuthError
    ApiNotFoundError = ApiNotFoundError

    @classmethod
    def get(cls, **auth):
        """
        Classmethod to get a connection from the pool or get a new one.
        The arguments must be the username and either the access_token or the
        password.
        If no correct connection can be created (or arguments are invalid), an
        ApiAuthError is raised.
        """

        # we only accept username+access_token or username+password
        keys = set(auth.keys())
        if keys not in (set(['username', 'access_token']), set(['username', 'password'])):
            raise Connection.ApiAuthError(u"Unable to start authenticattion (Wrong auth parameters ?")

        # we have a valid auth tuple, check if we have a matching one in
        # the pool and return it, or create a new one

        need_new = True

        if auth['username'] not in cls.pool:
            need_new = True
        else:
            con_auth = cls.pool[auth['username']]._authorization
            if con_auth:
                if 'access_token' in auth and not con_auth.startswith('token'):
                    need_new = True
                elif 'password' in auth and not con_auth.startswith('Basic'):
                    need_new = True
                else:
                    need_new = False

        if need_new:
            # createa new valid connection
            cls.pool[auth['username']] = cls(**auth)

        # return the old or new connection in the pool
        return cls.pool[auth['username']]

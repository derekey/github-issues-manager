from dateutil import parser, tz

from github import GitHub, ApiError, ApiAuthError, ApiNotFoundError

UTC = tz.gettz('UTC')


class Connection(GitHub):
    """
    A subclass of the default GitHub object to handle a pool of connections,
    one for each username
    """
    pool = {}
    ApiError = ApiError
    ApiAuthError = ApiAuthError
    ApiNotFoundError = ApiNotFoundError

    @staticmethod
    def parse_date(value):
        return parser.parse(value).replace(tzinfo=None)

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

    def __init__(self, username=None, password=None, access_token=None, client_id=None, client_secret=None, redirect_uri=None, scope=None):
        """
        Save auth informations in a dict to be able to retrieve it to generate
        a new connection (for example in async jobs)
        """
        self._connection_args = {}
        if username:
            self._connection_args['username'] = username
        if password:
            self._connection_args['password'] = password
        if access_token:
            self._connection_args['access_token'] = access_token
        super(Connection, self).__init__(username, password, access_token, client_id, client_secret, redirect_uri, scope)

    def _http(self, method, path, request_headers=None, response_headers=None, json_post=True, timeout=None, kw={}):
        api_error = None
        if response_headers is None:
            response_headers = {}
        try:
            return super(Connection, self)._http(method, path, request_headers, response_headers, json_post, timeout, kw)
        except ApiError, e:
            api_error = e
            raise
        except:
            raise
        finally:
            self.manage_token(
                path=path,
                method=method,
                request_headers=request_headers,
                response_headers=response_headers,
                kw=kw,
                api_error=api_error
            )

    def manage_token(self, *args, **kwargs):
        from core.limpyd_models import Token
        Token.update_token_from_gh(self, *args, **kwargs)


def parse_header_links(value):
    """
    Based on kennethreitz/requests stuff
    Return a dict of parsed link headers proxies.
    i.e. Link: <http:/.../front.jpeg>; rel=front; type="image/jpeg",<http://.../back.jpeg>; rel=back;type="image/jpeg"
    """

    links = {}

    replace_chars = " '\""

    for val in value.split(","):
        try:
            url, params = val.split(";", 1)
        except ValueError:
            url, params = val, ''

        link = {}

        link["url"] = url.strip("<> '\"")

        for param in params.split(";"):
            try:
                key, value = param.split("=")
            except ValueError:
                break

            link[key.strip(replace_chars)] = value.strip(replace_chars)

        if 'rel' in link:
            links[link['rel']] = link

    return links


def prepare_fetch_headers(if_modified_since=None, if_none_match=None, github_format=None):
    """
    Prepare and return the headers to use for the github call: return a dict
    with Accept, If-Modified-Since and If-None-Match
    """
    headers = {
        'Accept': 'application/vnd.github%s' % (github_format or '+json')
    }
    if if_modified_since:
        headers['If-Modified-Since'] = if_modified_since.replace(tzinfo=UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')
    if if_none_match:
        headers['If-None-Match'] = if_none_match

    return headers

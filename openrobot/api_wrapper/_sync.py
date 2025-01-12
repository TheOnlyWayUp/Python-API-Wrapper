import requests
import re
import warnings
import io
import typing
import time
from .error import *
from .results import *
from .translate import Translate
from .speech import Speech
from .utils import get_token_from_file

try:
    from urllib.parse import quote_plus as quote
except:
    try:
        from urllib.parse import quote
    except:
        quote = lambda s: s
        warnings.warn('urllib.parse.quote_plus and urllib.parse.quote cannot be found. Things might not be parsed well.')

class SyncClient:
    """Sync Client for OpenRobot API.

    Parameters
    ----------
    token: Optional[:class:`str`]
        The token to be used to authorize to the API. Defaults 
        to ``I-Am-Testing``.
    ignore_warning: Optional[:class:`bool`]
        Ignores the ``I-Am-Testing`` Warning. Defaults to ``False``.
    handle_ratelimit: Optional[:class:`bool`]
        Handles the ratelimit. If this is ``False``, then it raises
        :exc:`TooManyRequests`. Else, it will sleep for `Retry-After`. 
        Defaults to ``True``.
    tries: Optional[:class:`int`]
        The number of tries to execute a request to the API This is to. 
        handle 429s. This does not affect anything if ``handle_ratelimit``
        is ``False``. If this is ``None``, it will go infinitely and you
        might get Temp-Banned by Cloudflare. Defaults to ``5``.

    Attributes
    ----------
    token: :class:`str`
        The token used to authorize to the API.
    """

    def __init__(self, token: str = 'I-Am-Testing', *, ignore_warning = False, handle_ratelimit: bool = True, tries: int = 5):
        token = token or get_token_from_file()
        
        if not token:
            raise NoTokenProvided()
        elif token == 'I-Am-Testing' and not ignore_warning:
            warnings.warn('Using I-Am-Testing token will only let you 5 requests/day (UTC based, will reset on 00:00 UTC) for all `/api` methods and will raise an `openrobot.api_wrapper.error.Forbidden` after you have reached your limit.')

        self.token: str = str(token)

        self.handle_ratelimit: bool = handle_ratelimit

        self.tries: int = tries

    # Important and internal methods, but should be used un-regularly by the User itself.

    def _get_authorization_headers(self, token: str = None, *, header = True):
        token = str(token or self.token)
        if header is False:
            return f'token={token}'
        else:
            return {'Authorization': token}

    def _request(self, method: str, url: str, **kwargs):
        url = str(url)

        headers = self._get_authorization_headers()
        if kwargs.get('headers') and isinstance(kwargs.get('headers'), dict):
            hdr = kwargs.pop('headers')
            kwargs['headers'].update(headers)
        else:
            kwargs['headers'] = headers

        return_on = kwargs.pop('return_on', [])

        if not url.startswith('/'):
            url = url[1:]

        raw = kwargs.pop('raw', False)

        if not url.startswith('api/'):
            url = url[4:]

        if not re.match(rf'^http[s]?://[api.openrobot.xyz|lyrics.ayomerdeka.com]/', url) and not kwargs.pop('no_url_regex', False):
            url = ('https://api.openrobot.xyz/api' + url)
        else:
            raise TypeError('URL is not a valid HTTP/HTTPs URL.')

        tries = int(self.tries) if self.tries is not None else None

        while tries is None or tries > 0:
            with requests.Session() as s:
                r = s.request(method, url, **kwargs)

                js = r.json()

                if r.status_code in return_on:
                    if raw:
                        return r
                    else:
                        return js
                if r.status_code == 403:
                    raise Forbidden(r, js)
                elif r.status_code == 400:
                    raise BadRequest(r, js)
                elif r.status_code == 500:
                    raise InternalServerError(r, js)
                elif r.status_code == 429:
                    if not self.handle_ratelimit:
                        raise TooManyRequests(r, js)

                    try:
                        time.sleep(int(r.headers['Retry-After']))
                    except KeyError as e:
                        raise KeyError('Retry-After header is not present.') from e # this probably wont trigger, but either way we still need to handle it, right?

                    if tries:
                        tries -= 1
                elif 200 <= r.status_code < 300:
                    if raw:
                        return r
                    else:
                        return js
                else:
                    cls = OpenRobotAPIError(js)
                    cls.raw = js
                    cls.response = r

                    raise cls

        raise TooManyRequests(r, js)

    # Methods to query to API:

    def text_generation(self, text: str, *, max_length: typing.Optional[int] = None, num_return: typing.Optional[int] = 1) -> TextGenerationResult:
        """
        Text Generation/Completion. This uses the /api/text-generation endpoint.

        Parameters
        ----------
        text: :class:`str`
            The text to be completed/generated.
        max_length: Optional[:class:`int`]
            The maximum length of the generated text. Defaults to ``None``.
        num_return: Optional[:class:`int`]
            The number of generated texts to return. Defaults to 1.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`TextGenerationResult`
            The text generation result returned by the API.
        """

        js = self._request('POST', '/api/text-generation', data={'text': text, 'max_length': max_length, 'num_return': num_return})
        return TextGenerationResult(js)

    def text_generation_get(self, task_id: str) -> TextGenerationResult:
        """
        Gets the status of a text generation task. This uses the /api/text-generation/{task_id} endpoint.

        Parameters
        ----------
        task_id: :class:`str`
            The task ID of the text generation task.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`TextGenerationResult`
            The text generation result returned by the API.
        """

        js = self._request('GET', f'/api/text-generation/{quote(task_id)}')
        return TextGenerationResult(js)

    def sentiment(self, text: str) -> SentimentResult:
        """
        Performs a Sentiment check on a text.

        Parameters
        ----------
        text: :class:`str`
            The text to be checked.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`SentimentResult`
            The sentiment result returned by the API.
        """

        js = self._request('POST', '/api/sentiment', data={'text': text})
        return SentimentResult(js)

    def sentiment_get(self, task_id: str) -> SentimentResult:
        """
        Gets the status of a sentiment task. This uses the /api/sentiment/{task_id} endpoint.

        Parameters
        ----------
        task_id: :class:`str`
            The task ID of the sentiment task.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`SentimentResult`
            The sentiment result returned by the API.
        """

        js = self._request('GET', f'/api/sentiment/{quote(task_id)}')
        return SentimentResult(js)

    def summarization(self, text: str, *, max_length: typing.Optional[int] = None, min_length: typing.Optional[int] = 1) -> SummarizationResult:
        """
        Summarizes a text. This uses the /api/summarization endpoint.

        Parameters
        ----------
        text: :class:`str`
            The text to be summarized.
        max_length: Optional[:class:`int`]
            The maximum length of the summary. Defaults to ``None``.
        min_length: Optional[:class:`int`]
            The minimum length of the summary. Defaults to ``None``.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`SummarizationResult`
            The summarization result returned by the API.
        """

        js = self._request('POST', '/api/summarization', data={'text': text, 'max_length': max_length, 'min_length': min_length})
        return SummarizationResult(js)

    def summarization_get(self, task_id: str) -> SummarizationResult:
        """
        Gets the status of a summarization task. This uses the /api/summarization/{task_id} endpoint.

        Parameters
        ----------
        task_id: :class:`str`
            The task ID of the summarization task.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`SummarizationResult`
            The summarization result returned by the API.
        """

        js = self._request('GET', f'/api/summarization/{quote(task_id)}')
        return SummarizationResult(js)

    def lyrics(self, query: str) -> LyricResult:
        """
        Gets the lyrics from the API.

        Parameters
        ----------
        query: :class:`str`
            Searches for the lyrics from the query.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`LyricResult`
            The Lyrics Result returned by the API.
        """

        js = self._request('GET', f'/api/lyrics/{quote(query)}')
        return LyricResult(js)

    def nsfw_check(self, url: str) -> NSFWCheckResult:
        """
        Queries an NSFW Check to the API.

        Parameters
        ----------
        url: :class:`str`
            The Image URL to check for.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`NSFWCheckResult`
            The NSFW Check Result returned by the API.
        """

        js = self._request('GET', '/api/nsfw-check', params={'url': url})
        return NSFWCheckResult(js)

    def celebrity(self, url: str) -> typing.List[CelebrityResult]:
        """
        Detects the celebrities in the image.

        Parameters
        ----------
        url: :class:`str`
            The Image URL.      

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        List[:class:`CelebrityResult`]
            The celebrities detected.
        """

        js = self._request('GET', '/api/celebrity', params={'url': url})
        return [CelebrityResult(data) for data in js['detectedFaces']]

    def ocr(self, source: typing.Union[str, io.BytesIO]) -> OCRResult:
        """
        Reads text from a image.

        Parameters
        ----------
        source: Union[:class:`str`, :class:`io.BytesIO`]
            The URL/Bytes of the image.

        Raises
        ------
        :exc:`Forbidden`
            API Returned a 403 HTTP Status Code.
        :exc:`BadRequest`
            API Returned a 400 HTTP Status Code.
        :exc:`InternalServerError`
            API Returned a 500 HTTP Status Code.

        Returns
        -------
        :class:`OCRResult`
            The OCR/Text found.
        """

        if isinstance(source, str):
            js = self._request('POST', '/api/ocr', params={'url': source})
        elif isinstance(source, io.BytesIO):
            js = self._request('POST', '/api/ocr', files={'upload_file': getattr(source, 'getvalue', lambda: source)()})
        else:
            raise OpenRobotAPIError('source must be a URL or BytesIO.')

        return OCRResult(js)

    @property
    def translate(self):
        """:class:`Translate`: The Translate client."""
        return Translate(self, False)

    @property
    def speech(self) -> Speech:
        """:class:`Speech`: The Speech client."""
        return Speech(self, False)

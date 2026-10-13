from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default 50 per page, client may ask for fewer/more via ?page_size=,
    but never more than 100 (so ?page_size=100000 cannot dump a whole table).

    Response shape: {"count", "next", "previous", "results"}.

    Applied per-view (not globally) so list endpoints that existing frontend
    pages expect as plain arrays keep returning plain arrays.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

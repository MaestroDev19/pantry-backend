from typing import Any

class Client:
    auth: Any

    def table(self, table_name: str) -> Any: ...
    def rpc(self, fn: str, params: dict[str, Any] | None = ...) -> Any: ...

def create_client(
    supabase_url: str,
    supabase_key: str,
    options: Any | None = ...,
) -> Client: ...

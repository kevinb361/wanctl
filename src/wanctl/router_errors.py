"""Explicit exceptions shared by RouterOS transport and failover layers.

Transport-failure contract (ASSESS-004 / REM-006)
-------------------------------------------------
``RouterTransportError`` is the single normalized signal for a *retryable*
RouterOS transport failure. It is deliberately NOT a ``requests`` exception so
it passes through the ``except requests.RequestException`` handlers inside the
``RouterOSREST`` command handlers, which otherwise degrade a dead link into an
indistinguishable ``(1, "", "Command failed")`` tuple.

Where it is raised:
    ``RouterOSREST._request`` -- the one normalization point, when the
    underlying session raises a request error classified retryable by
    ``retry_utils.is_retryable_error``.

Where it surfaces:
    ``RouterOSREST.run_cmd`` only. Its ``retry_with_backoff`` decorator
    exhausts the bounded REST attempts first, then re-raises so
    ``FailoverRouterClient.run_cmd`` performs exactly one transport switch.

Where it is contained:
    Every other public ``RouterOSREST`` method (``test_connection``,
    ``set_queue_limit``, ``get_queue_stats``, ``get_queue_types``,
    ``set_queue_type_params``, ``find_mangle_rule_id``) keeps its legacy
    ``False``/``None`` failure contract for direct (non-failover) callers such
    as the ``wanctl-check-cake`` tools.
"""


class RouterTransportError(ConnectionError):
    """Retryable RouterOS transport failure after request-level normalization.

    Subclasses builtin ``ConnectionError`` so ``retry_utils.is_retryable_error``
    classifies it retryable without any message inspection.
    """


__all__ = ["RouterTransportError"]

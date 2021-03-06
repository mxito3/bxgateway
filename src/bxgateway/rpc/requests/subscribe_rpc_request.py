from typing import TYPE_CHECKING, Callable, Any, Dict
from bxutils import logging
from bxcommon.rpc.bx_json_rpc_request import BxJsonRpcRequest
from bxcommon.rpc.json_rpc_response import JsonRpcResponse
from bxcommon.rpc.requests.abstract_rpc_request import AbstractRpcRequest
from bxcommon.rpc.rpc_errors import RpcInvalidParams, RpcAccountIdError
from bxgateway.feed.feed_manager import FeedManager
from bxgateway.feed.subscriber import Subscriber
from bxutils.logging.log_record_type import LogRecordType

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    # pylint: disable=ungrouped-imports,cyclic-import
    from bxgateway.connections.abstract_gateway_node import AbstractGatewayNode

logger = logging.get_logger(__name__)
logger_filters = logging.get_logger(LogRecordType.TransactionFiltering, __name__)


class SubscribeRpcRequest(AbstractRpcRequest["AbstractGatewayNode"]):
    help = {
        "params": '[feed_name, {"include": [field_1, field_2], "duplicates": false, "include_from_blockchain": true}].\n'
        "Available feeds: newTxs, pendingTxs, newBlocks, ethOnBlock\n"
        "Available fields for transaction feeds: tx_hash, tx_contents (default: all)\n"
        "Available fields for block feed: hash, block (default: all)\n"
        "duplicates: false (filter out duplicates from feed, typically low fee "
        "transactions, default), true (include all duplicates)\n"
        "include_from_blockchain: include transactions received from the connected blockchain node (default: true)\n",
        "description": "Subscribe to a named feed for notifications",
    }

    def __init__(
        self,
        request: BxJsonRpcRequest,
        node: "AbstractGatewayNode",
        feed_manager: FeedManager,
        subscribe_handler: Callable[[Subscriber, str], None],
    ) -> None:
        self.feed_name = ""
        self.feed_manager = feed_manager
        self.subscribe_handler = subscribe_handler
        self.options = {}

        super().__init__(request, node)

        assert self.feed_name != ""

    def validate_params(self) -> None:
        if not self.feed_manager.feeds:
            raise RpcAccountIdError(
                self.request_id,
                f"Account does not have access to the transaction streaming service.",
            )

        params = self.params
        if not isinstance(params, list) or len(params) != 2:
            raise RpcInvalidParams(
                self.request_id,
                "Subscribe RPC request params must be a list of length 2.",
            )

        feed_name, options = params
        feed = self.feed_manager.feeds.get(feed_name)
        if feed is None:
            raise RpcInvalidParams(
                self.request_id,
                f"{feed_name} is an invalid feed. "
                f"Available feeds: {list(self.feed_manager.feeds)}",
            )

        self.node.on_new_subscriber_request()

        self.feed_name = feed_name

        available_fields = self.feed_manager.get_feed_fields(feed_name)
        invalid_options = RpcInvalidParams(
            self.request_id,
            f"{options} is not a valid set of options. "
            'Valid format/fields: {"include": '
            f"{available_fields}"
            "}.",
        )
        if not isinstance(options, dict):
            raise invalid_options

        include = options.get("include", None)
        if include is not None:
            if not isinstance(include, list):
                raise invalid_options

            if any(
                included_field not in available_fields for included_field in include
            ):
                raise invalid_options
        filters = options.get("filters", None)
        if filters:
            logger_filters.debug(filters)
            formatted_filters = self.format_filters(filters)
            logger_filters.debug("formatted filters: {}", formatted_filters)
            options["filters"] = formatted_filters
        self.options = options

    async def process_request(self) -> JsonRpcResponse:
        params = self.params
        assert isinstance(params, list)

        subscriber = self.feed_manager.subscribe_to_feed(self.feed_name, self.options)
        assert subscriber is not None  # already validated
        self.subscribe_handler(subscriber, self.feed_name)

        return JsonRpcResponse(self.request_id, subscriber.subscription_id)

    def format_filters(self, filters: Any) -> Dict[str, Any]:
        valid_filters = self.feed_manager.get_valid_feed_filters(self.feed_name)
        invalid_filters = RpcInvalidParams(
            self.request_id,
            f"{filters} is not a valid set of filters. "
            'Valid format/filters: {"include": '
            f"{valid_filters}"
            "}.",
        )

        if not isinstance(filters, dict):
            raise invalid_filters
        if not valid_filters:
            raise invalid_filters
        logger_filters.debug("Formatting filters")
        try:
            filters = self.feed_manager.reformat_feed_filters(self.feed_name, filters)
        except Exception:
            raise invalid_filters
        return filters

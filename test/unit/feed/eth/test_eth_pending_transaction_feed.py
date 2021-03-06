from unittest.mock import MagicMock

from bxcommon.test_utils import helpers
from bxcommon.test_utils.abstract_test_case import AbstractTestCase
from bxcommon.test_utils.helpers import async_test
from bxcommon.utils import convert
from bxcommon.utils.alarm_queue import AlarmQueue
from bxcommon.utils.object_hash import Sha256Hash
from bxgateway.feed.eth.eth_pending_transaction_feed import EthPendingTransactionFeed
from bxgateway.feed.eth.eth_raw_transaction import EthRawTransaction
from bxgateway.feed.new_transaction_feed import FeedSource
from bxgateway.testing.mocks import mock_eth_messages
from bxutils import logging

logger = logging.get_logger()

SAMPLE_TRANSACTION_FROM_WS = {
    "from": "0xbd4e113ee68bcbbf768ba1d6c7a14e003362979a",
    "gas": "0x9bba",
    "gasPrice": "0x41dcf5dbe",
    "hash": "0x0d96b711bdcc89b59f0fdfa963158394cea99cedce52d0e4f4a56839145a814a",
    "input": "0xea1790b90000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000005ee3f95400000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000041d880a37ae74a2593900da75b3cae6335b5f58997c6f426e98e42f55d3d5cd6487369ec0250a923cf1f45a39aa551b68420ec04582d1a68bcab9a70240ae39f261b00000000000000000000000000000000000000000000000000000000000000",
    "nonce": "0x1e8",
    "r": "0x561fc2c4428e8d3ff1e48ce07322a98ea6c8c5836bc79e7d60a6ed5d37a124a2",
    "s": "0x7ab1477ccb14143ba9afeb2f98099c85dd4175f09767f03d47f0733467eadde2",
    "to": "0xd7bec4d6bf6fc371eb51611a50540f0b59b5f896",
    "v": "0x25",
    "value": "0x0"
}


class EthPendingTransactionFeedTest(AbstractTestCase):

    def setUp(self) -> None:
        self.alarm_queue = AlarmQueue()
        self.sut = EthPendingTransactionFeed(self.alarm_queue)

    @async_test
    async def test_publish_transaction_bytes(self):
        subscriber = self.sut.subscribe({})

        tx_message = mock_eth_messages.generate_eth_tx_message()
        tx_hash_str = f"0x{str(tx_message.tx_hash())}"

        self.sut.publish(
            EthRawTransaction(tx_message.tx_hash(), tx_message.tx_val(), FeedSource.BDN_SOCKET)
        )

        received_tx = await subscriber.receive()
        self.assertEqual(tx_hash_str, received_tx["tx_hash"])
        self.assertEqual(tx_hash_str, received_tx["tx_contents"]["hash"])
        self.assertIn("from", received_tx["tx_contents"])
        self.assertIn("gas", received_tx["tx_contents"])
        self.assertIn("gas_price", received_tx["tx_contents"])
        self.assertIn("input", received_tx["tx_contents"])
        self.assertIn("value", received_tx["tx_contents"])
        self.assertIn("to", received_tx["tx_contents"])
        self.assertIn("nonce", received_tx["tx_contents"])
        self.assertIn("v", received_tx["tx_contents"])
        self.assertIn("r", received_tx["tx_contents"])
        self.assertIn("s", received_tx["tx_contents"])

    @async_test
    async def test_publish_transaction_dictionary(self):
        subscriber = self.sut.subscribe({})

        transaction_hash_str = SAMPLE_TRANSACTION_FROM_WS["hash"]
        transaction_hash = Sha256Hash(
            convert.hex_to_bytes(transaction_hash_str[2:])
        )

        self.sut.publish(
            EthRawTransaction(transaction_hash, SAMPLE_TRANSACTION_FROM_WS, FeedSource.BLOCKCHAIN_RPC)
        )

        received_tx = await subscriber.receive()
        self.assertEqual(transaction_hash_str, received_tx["tx_hash"])
        self.assertEqual(transaction_hash_str, received_tx["tx_contents"]["hash"])
        self.assertIn("from", received_tx["tx_contents"])
        self.assertIn("gas", received_tx["tx_contents"])
        self.assertIn("gas_price", received_tx["tx_contents"])
        self.assertIn("input", received_tx["tx_contents"])
        self.assertIn("value", received_tx["tx_contents"])
        self.assertIn("to", received_tx["tx_contents"])
        self.assertIn("nonce", received_tx["tx_contents"])
        self.assertIn("v", received_tx["tx_contents"])
        self.assertIn("r", received_tx["tx_contents"])
        self.assertIn("s", received_tx["tx_contents"])

    @async_test
    async def test_publish_transaction_no_subscribers(self):
        self.sut.serialize = MagicMock(wraps=self.sut.serialize)

        self.sut.publish(mock_eth_messages.generate_eth_raw_transaction())

        self.sut.serialize.assert_not_called()

    @async_test
    async def test_publish_transaction_duplicate_transaction(self):
        self.sut.subscribe({})

        self.sut.serialize = MagicMock(wraps=self.sut.serialize)
        raw_transaction = mock_eth_messages.generate_eth_raw_transaction()

        self.sut.publish(raw_transaction)
        self.sut.publish(raw_transaction)

        self.sut.serialize.assert_called_once()

    @async_test
    async def test_publish_duplicate_transaction_subscriber_wants_duplicates(self):
        subscriber = self.sut.subscribe({"duplicates": True})

        self.sut.serialize = MagicMock(wraps=self.sut.serialize)
        subscriber.queue = MagicMock(wraps=subscriber.queue)
        raw_transaction = mock_eth_messages.generate_eth_raw_transaction()

        self.sut.publish(raw_transaction)
        self.sut.serialize.assert_called_once()
        self.sut.serialize.reset_mock()
        subscriber.queue.assert_called_once()
        subscriber.queue.reset_mock()

        self.sut.publish(raw_transaction)
        self.sut.serialize.assert_called_once()
        subscriber.queue.assert_called_once()

    @async_test
    async def test_publish_invalid_transaction(self):
        subscriber = self.sut.subscribe({})

        transaction_hash = helpers.generate_object_hash()
        transaction_contents = helpers.generate_bytearray(250)

        self.sut.publish(
            EthRawTransaction(transaction_hash, transaction_contents, FeedSource.BLOCKCHAIN_SOCKET)
        )

        self.assertEqual(0, subscriber.messages.qsize())

    @async_test
    async def test_publish_transaction_filtered_transaction(self):
        to = "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be"
        subscriber = self.sut.subscribe({"filters": {"to": to}})
        self.sut.serialize = MagicMock(wraps=self.sut.serialize)
        subscriber.queue = MagicMock(wraps=subscriber.queue)
        raw_transaction = \
            mock_eth_messages.generate_eth_raw_transaction_with_to_address(FeedSource.BLOCKCHAIN_SOCKET,
                                                                           "3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be")

        self.sut.publish(raw_transaction)
        received_tx = await subscriber.receive()
        self.assertTrue(received_tx)
        self.assertEqual(received_tx["tx_contents"].get("to", None), to)
        self.sut.serialize.assert_called_once()
        self.sut.serialize.reset_mock()
        subscriber.queue.assert_called_once()

    @async_test
    async def test_publish_transaction_denied_transaction(self):
        to = "0x1111111111111111111111111111111111111111"
        subscriber = self.sut.subscribe({"filters": {"to": to}})
        self.sut.serialize = MagicMock(wraps=self.sut.serialize)
        subscriber.queue = MagicMock(wraps=subscriber.queue)
        raw_transaction = \
            mock_eth_messages.generate_eth_raw_transaction_with_to_address(FeedSource.BLOCKCHAIN_SOCKET,
                                                                           "3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be")

        self.sut.publish(raw_transaction)
        subscriber.queue.assert_not_called()


    @async_test
    async def test_validate_and_handle_filters(self):
        filters_test = {
            "AND": [
                {"to": ["dai", "eth"]},
                {
                    "OR": [
                        {"transaction_value_range_eth": ['0', '1']},
                        {"from": ['0x8fdc5df186c58cdc2c22948beee12b1ae1406c6f',
                                  '0x77e2b72689fc954c16b37fbcf1b0b1d395a0e288']},
                    ]
                }
            ]
        }
        f = {"AND": [{"transaction_value_range_eth": ["187911390000000000", "450550050000000000"]}]}

        valid = self.sut.reformat_filters(filters_test)
        self.assertTrue(valid)

        valid = self.sut.reformat_filters(f)
        self.assertTrue(valid)

        filters_test = {
            "AND": [
                {"to": ["dai", "eth"]},
                {
                    "OR": [
                        {"hello": [0.0, 2.1]},
                        {"from": ['0x8fdc5df186c58cdc2c22948beee12b1ae1406c6f',
                                  '0x77e2b72689fc954c16b37fbcf1b0b1d395a0e288']},
                    ]
                }
            ]
        }
        with self.assertRaises(Exception):
            self.sut.reformat_filters(filters_test)


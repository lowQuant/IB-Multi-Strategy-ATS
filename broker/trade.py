# ATS/broker/trade.py
from ib_insync import *
from gui.log import add_log

class TradeManager:
    def __init__(self, ib_client):
        self.ib = ib_client

    def place_order(self, contract, quantity, order_type='MKT', urgency='Patient', orderRef="", limit=None):
        """
        Place an Order on the exchange via ib_insync.

        :param contract: ib.Contract
        :param quantity: order size as a signed integer (quantity > 0 means 'BUY' and quantity < 0 means 'SELL')
        :param order_type: order type such as 'LMT', 'MKT' etc.
        :param urgency: 'Patient' (default), 'Normal', 'Urgent'
        :param limit: if order_type 'LMT' state limit as float
        """
        self.ib.qualifyContracts(contract)

        # Create order object
        action = 'BUY' if quantity > 0 else 'SELL'
        totalQuantity = int(abs(quantity))

        if order_type == 'LMT':
            assert limit, "Limit price must be specified for limit orders."
            lmtPrice = float(limit)
            order = LimitOrder(action, totalQuantity, lmtPrice)
        elif order_type == 'MKT':
            order = MarketOrder(action, totalQuantity)

        order.algoStrategy = 'Adaptive'
        if urgency == 'Normal':
            order.algoParams = [TagValue('adaptivePriority', 'Normal')]
        elif urgency == 'Urgent':
            order.algoParams = [TagValue('adaptivePriority', 'Urgent')]
        else:
            order.algoParams = [TagValue('adaptivePriority', 'Patient')]

        order.orderRef = orderRef

        # Place the order
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(1)
        return trade

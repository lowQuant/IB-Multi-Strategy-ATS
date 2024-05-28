# ATS/broker/trademanager.py
from ib_insync import *
from gui.log import add_log
import time

class TradeManager:
    def __init__(self, ib_client,strategy_manager):
        self.ib = ib_client
        self.strategy_manager = strategy_manager

    def trade(self, contract, quantity, order_type='MKT', algo = True, urgency='Patient', orderRef="", limit=None, useRth = False):
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

        if algo:
            order.algoStrategy = 'Adaptive'
            if urgency == 'Normal':
                order.algoParams = [TagValue('adaptivePriority', 'Normal')]
            elif urgency == 'Urgent':
                order.algoParams = [TagValue('adaptivePriority', 'Urgent')]
            else:
                order.algoParams = [TagValue('adaptivePriority', 'Patient')]

        order.orderRef = orderRef
        order.useRth = useRth

        # Place the order
        trade = self.ib.placeOrder(contract, order)
        time.sleep(1)
        self.ib.sleep(1)

        # Notify the strategy manager about the order placement
        self.strategy_manager.message_queue.put({
            'type': 'order',
            'strategy': orderRef,
            'trade': trade,
            'contract': contract,
            'order': order,
            'info': 'sent from TradeManager'
        })
        
        return trade

    def roll_future(self, current_contract, new_contract, orderRef=""):
        """
            Roll a futures contract by closing the current contract and opening a new one.
            :param current_contract: The current ib_insync.Contract to be closed.
            :param new_contract: The new ib_insync.Contract to be opened.
            :param orderRef: Reference identifier for the order.
        """
        # Qualify contracts
        self.ib.qualifyContracts(current_contract,new_contract)

        # Define quantity based on current position
        quantity = [pos.position for pos in self.ib.portfolio() if pos.contract.localSymbol==current_contract.localSymbol][0]

        # Define the combination contract (bag)
        bag = Contract(symbol=current_contract.symbol, secType='BAG', exchange='SMART', currency=current_contract.currency)
        bag.comboLegs = [
            ComboLeg(conId=current_contract.conId, ratio=1, action="SELL" if quantity > 0 else "BUY",exchange=current_contract.exchange),  # Exiting the current contract
            ComboLeg(conId=new_contract.conId, ratio=1, action="BUY" if quantity > 0 else "SELL",exchange=new_contract.exchange)        # Entering the new contract
        ]

        # Create the order - here we use a Market order as an example
        order = MarketOrder('BUY', abs(quantity))
        order.orderRef = orderRef

        # Place the order
        trade = self.ib.placeOrder(bag, order)
        return bag, order
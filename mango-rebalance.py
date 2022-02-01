import time
import mango
from decimal import Decimal
from mango import InstrumentValue

############################
#### Author: PattoMotto ####
############################

REBALANCE_TARGET_PERCENTAGE = 0.005 # e.g. 0.01 = 1% change in asset
SLEEP_SECOND = 30
SYMBOL = 'SOL/USDC'
ASSET_CURRENCY = 'SOL'
QOUTE_CURRENCY = 'USDC'

wallet = mango.Wallet.load("id.json")
# Create a 'devnet' Context
context = mango.ContextBuilder.build(cluster_name="devnet")

######### FUNCTION #########

def round(instrument_value: InstrumentValue):
    return instrument_value.token.round(instrument_value.value)

def get_size(quote_value: Decimal, price: mango.Price):
    return quote_value/price.mid_price

def create_order(market_operations: mango.MarketOperations, side: mango.Side, price: Decimal, quantity: Decimal, order_type: mango.OrderType):
    order = mango.Order.from_basic_info(side=side,
                                        price=price,
                                        quantity=quantity,
                                        order_type=order_type)
    placed_order = market_operations.place_order(order)
    print("\n\nplaced_order\n\t", placed_order)

def create_market_order(market_operations: mango.MarketOperations, side: mango.Side, price: Decimal, quantity: Decimal):
    create_order(market_operations=market_operations,
                 side=side,
                 price=price,
                 quantity=quantity,
                 order_type=mango.OrderType.MARKET)

def create_buy_market_order(market_operations: mango.MarketOperations, quote_value: Decimal, price: mango.Price):
    create_market_order(market_operations=market_operations,
                        side=mango.Side.BUY,
                        price=price.mid_price,
                        quantity=get_size(quote_value,price))

def create_sell_market_order(market_operations: mango.MarketOperations, quote_value: Decimal, price: mango.Price):
    create_market_order(market_operations=market_operations,
                        side=mango.Side.SELL,
                        price=price.mid_price,
                        quantity=get_size(quote_value,price))

def show_current_price(pyth_oracle: mango.Oracle, ftx_oracle: mango.Oracle, spot_oracle: mango.Oracle):
    print(f'{SYMBOL} price on Pyth is:\n\t{pyth_oracle.fetch_price(context)}')
    print(f'{SYMBOL} price on FTX is:\n\t{ftx_oracle.fetch_price(context)}')
    print(f'{SYMBOL} price on Serum is:\n\t{spot_oracle.fetch_price(context)}')
######### FUNCTION #########

# Load the market
stub = context.market_lookup.find_by_symbol(SYMBOL)
market = mango.ensure_market_loaded(context, stub)

pyth = mango.create_oracle_provider(context, "pyth")
pyth_oracle = pyth.oracle_for_market(context, market)
# Note that Pyth provides a +/- confidence interval
print(f'{SYMBOL} price on Pyth is:\n\t{pyth_oracle.fetch_price(context)}')

ftx = mango.create_oracle_provider(context, "ftx")
ftx_oracle = ftx.oracle_for_market(context, market)
print(f'{SYMBOL} price on FTX is:\n\t{ftx_oracle.fetch_price(context)}')

# The 'market' oracle accesses the market's bids and asks, and our
# market-type for "BTC/USDC" is spot.
spot = mango.create_oracle_provider(context, "market")
spot_oracle = spot.oracle_for_market(context, market)
print(f'{SYMBOL} price on Serum is:\n\t{spot_oracle.fetch_price(context)}')

asset_token = context.instrument_lookup.find_by_symbol_or_raise(ASSET_CURRENCY)
print("asset_token", asset_token)

# token_accounts = mango.TokenAccount.fetch_all_for_owner_and_token(context, wallet.address, asset_token)
# print(token_accounts)
# print(token_accounts[0])


# Mango accounts are per-Group, so we need to load the Group first.
group = mango.Group.load(context)

def loop():

    # Get all the Wallet's accounts for that Group
    accounts = mango.Account.load_all_for_owner(context, wallet.address, group)
    account = accounts[0]
    market_operations = mango.create_market_operations(context, wallet, account, market, dry_run=False)
    print(market_operations.load_orderbook())

    quote_token = account.shared_quote.net_value.token

    # Find the ASSET details in the account
    asset_balance = 0
    for slot in account.slots:
        if slot.base_instrument == asset_token:
            asset_balance = round(slot.net_value)

    show_current_price(pyth_oracle, ftx_oracle, spot_oracle)

    print("Asset balance", asset_balance, asset_token.name)
    price = spot_oracle.fetch_price(context)
    asset_value = asset_token.round(price.mid_price * asset_balance)
    print("Asset value", asset_value, quote_token.name)
    quote_value = round(accounts[0].shared_quote.net_value)
    print("Shared quote token", quote_value, quote_token.name)

    portfolio_value = asset_value + quote_value
    print("Portfolio value", quote_token.round(portfolio_value), quote_token.name)

    target_value = portfolio_value * Decimal(0.5)
    offset = asset_value - target_value
    offset_percentage = abs(offset/target_value)
    print('offset', offset, f'offset_percentage {offset_percentage*100:.2f}%')
    if offset > 0 and offset_percentage >= REBALANCE_TARGET_PERCENTAGE:
        print('Take profit for', offset, quote_token.name)
        create_sell_market_order(market_operations=market_operations, quote_value=offset, price=price)
    elif offset < 0 and offset_percentage >= REBALANCE_TARGET_PERCENTAGE:
        print('Buy more with', abs(offset), quote_token.name)
        create_buy_market_order(market_operations=market_operations, quote_value=abs(offset), price=price)
    else:
        print('Wait...')

while True:
    loop()
    time.sleep(SLEEP_SECOND)
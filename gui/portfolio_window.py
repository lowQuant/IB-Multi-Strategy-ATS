import tkinter as tk
from tkinter import ttk
import pandas as pd
from datetime import datetime
from data_and_research import ac, fetch_strategies

def on_combobox_select(tree, strategy, row_id):
    # Get the symbol from the row
    symbol = tree.set(row_id, 'symbol')
    row = tree.item(row_id)
    print(f"Selected Strategy: {strategy}, Row data: {row}")

    
def open_portfolio_window(strategy_manager):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("800x400")

    # Fetch the account values
    cash = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "TotalCashValue")
    total_equity = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "EquityWithLoanValue")
    margin = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "InitMarginReq")

    # Create a frame for account information
    account_info_frame = tk.Frame(window)
    account_info_frame.pack(side=tk.BOTTOM, fill=tk.X)

    # Labels for account information
    tk.Label(account_info_frame, text=f"NAV: {total_equity:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"  Cash: {cash:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"  Margin: {margin:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"Date: {datetime.now().strftime('%Y-%m-%d')}").pack(side=tk.RIGHT)

    portfolio_data = get_portfolio_data(strategy_manager)  # Fetch the data
    strategies,_ = fetch_strategies()  # Fetch list of strategies
    strategies.append("")

    # Add a scrollbar
    scrollbar = tk.Scrollbar(window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create the treeview
    columns = ("symbol", "Asset Class", "position", "NAV share",'Average Cost','market Price','pnl %',"strategy")
    tree = ttk.Treeview(window, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Define the column headings
    for col,w in zip(columns,[50,120,60,60,60,60,60,100]):
        tree.column(col, stretch=tk.YES, minwidth=0, width=w)  # Adjust the width as needed
        tree.heading(col, text=col.capitalize())

    # Adding data to the treeview
    for item in portfolio_data:
        #!  TODO: WRITE A FUNCTION: match_position_with_db
        # in this function it will check the db for an entry in the symbol and asset class
        # if no entry we can proceed as below. if one entry do item.position - entry.position and display the result in a row
        # display the residual in the next row - user has to select a strategy for that
        # also calculate avg px etc.

        row_id = tree.insert("", tk.END, values=(item["symbol"], item["asset class"], item["position"], f"{item['% of nav']:.2f}",
                            f"{item['averageCost']:.2f}", f"{item['marketPrice']:.2f}", f"{item['pnl %']:.2f}",""))

    # After adding all items to the treeview
    window.update_idletasks()  # Update the GUI to ensure treeview is drawn

    # Add a strategy dropdown for each row in a separate column
    def on_strategy_cell_click(event):
        # Get the row and column clicked
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            row = tree.identify_row(event.y)
            if tree.heading(column, "text").lower() == "strategy":
                # Position the combobox
                x, y, width, height = tree.bbox(row, column)
                pady = height // 2

                # Create a Combobox widget
                strategy_cb = ttk.Combobox(window, values=strategies)
                strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)

                # Set the current strategy if assigned, e.g., from a database
                current_strategy = " "  # Example placeholder
                strategy_cb.set(current_strategy)

                # Bind the selection event
                strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(tree, strategy_cb.get(), row))

    tree.bind("<Button-1>", on_strategy_cell_click)

    scrollbar.config(command=tree.yview)

def get_portfolio_data(strategy_manager):
    df = strategy_manager.portfolio_manager.get_ib_positions_for_gui()
    data_list = df.to_dict('records')
    print(data_list)
    return data_list

def get_strategies(arctic_lib):
    # Fetch list of strategies from ArcticDB
    pass

def assign_strategy(item_id, strategy):
    print(f"from assign_strategy func: {item_id}")
    # Function to assign a strategy to a portfolio item and update in ArcticDB
    pass

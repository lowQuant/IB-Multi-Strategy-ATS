import tkinter as tk
from tkinter import ttk
import pandas as pd
from datetime import datetime
from data_and_research import ac, fetch_strategies
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

def on_combobox_select(tree, strategy, row_id):
    '''this function is triggered via click on a strategy field
       and assigns a strategy to a position in our arcticdb''' # works
    # Get the symbol from the row
    symbol = tree.set(row_id, 'symbol')
    asset_class = tree.set(row_id, 'Asset Class')
    position = float(tree.set(row_id, 'position'))
    positions_df = ac.get_library('portfolio').read('positions').data

   # Filter the DataFrame for the row that matches our criteria
    filter_cond = (positions_df['symbol'] == symbol) & \
                  (positions_df['asset class'] == asset_class) & \
                  (positions_df['position'] == position)
    filtered_df = positions_df.loc[filter_cond]

    # Check if there are any rows to update
    if not filtered_df.empty:
        # Update the strategy for the filtered rows
        positions_df.loc[filter_cond, 'strategy'] = strategy

    ac.get_library('portfolio').write('positions', positions_df, metadata={'updated': 'strategy assignment from gui'})
    print(f"Strategy '{strategy}' assigned to position with symbol '{symbol}', asset class '{asset_class}', position {position}")

def refresh_portfolio_data(tree, strategy_manager):
    # Fetch the updated portfolio data
    portfolio_data = get_portfolio_data(strategy_manager)
    df = pd.DataFrame(portfolio_data)
    
    # Clear the current tree view contents
    for i in tree.get_children():
        tree.delete(i)
    
    # Re-populate the tree view with the new data
    for item in portfolio_data:
        tree.insert("", tk.END, values=(item["symbol"], item["asset class"], item["position"],
                                        item['currency'], f"{item['% of nav']:.2f}", 
                                        f"{item['marketPrice']:.2f}", f"{item['averageCost']:.2f}",
                                        f"{item['pnl %']:.2f}", item['strategy']))    

def show_pnl_graph(strategy_manager, window):
    # Here you would retrieve PnL data from ArcticDB and plot it
    pnl_lib = ac.get_library('pnl')
    pnl_df = pnl_lib.read(strategy_manager.ib_client.managedAccounts()[0]).data
    #pnl_df.set_index('timestamp', inplace=True)
    
    fig, ax = plt.subplots()
    pnl_df['total_equity'].plot(ax=ax)  # Plotting the total equity column
    ax.set_title('PnL Graph')
    ax.set_xlabel('Date')
    ax.set_ylabel('Total Equity')
    
    # Embed the plot into the Tkinter window
    canvas = FigureCanvasTkAgg(fig, master=window)  
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    canvas.draw()

def create_info_bar(strategy_manager,tab_control):
    # Fetch the account values
    cash = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "TotalCashValue")
    total_equity = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "EquityWithLoanValue")
    margin = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "InitMarginReq")

    account_info_frame = tk.Frame(tab_control)
    account_info_frame.pack(side=tk.BOTTOM, fill=tk.X)

    info_and_controls_frame = tk.Frame(account_info_frame)
    info_and_controls_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    date_label = tk.Label(info_and_controls_frame, text=f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    date_label.pack(side=tk.RIGHT, padx=5)

    # refresh_button = tk.Button(info_and_controls_frame, text="Refresh", command=lambda: refresh_portfolio_data(tree, strategy_manager))
    # refresh_button.pack(side=tk.RIGHT, padx=5)

    # Pack the NAV, Cash, and Margin labels into the account_info_frame
    tk.Label(account_info_frame, text=f"NAV: {total_equity:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f" Cash: {cash:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f" Margin: {margin:.2f}").pack(side=tk.LEFT)

    return info_and_controls_frame

def populate_portfolio_tab(window,strategy_manager,portfolio_tab,info_and_controls_frame):
    portfolio_data = get_portfolio_data(strategy_manager)  # Fetch the data
    df = pd.DataFrame(portfolio_data)
    strategies,_ = fetch_strategies()  # Fetch list of strategies
    strategies.append("")

    # Add a scrollbar
    scrollbar = tk.Scrollbar(portfolio_tab)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create the treeview
    columns = ("symbol", "Asset Class", "position", "FX" ,"Weight (%)",'Price','Cost','pnl %',"strategy")
    tree = ttk.Treeview(portfolio_tab, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Define the column headings
    for col,w in zip(columns,[50,120,60,50,60,60,60,60,100]):
        tree.column(col, stretch=tk.YES, minwidth=0, width=w)  # Adjust the width as needed
        tree.heading(col, text=col.capitalize())

    # Adding data to the treeview
    for item in portfolio_data:
        row_id = tree.insert("", tk.END, values=(item["symbol"], item["asset class"], item["position"], item['currency'],f"{item['% of nav']:.2f}",
                            f"{item['marketPrice']:.2f}", f"{item['averageCost']:.2f}", f"{item['pnl %']:.2f}",item['strategy']))

    refresh_button = tk.Button(info_and_controls_frame, text="Refresh", command=lambda: refresh_portfolio_data(tree, strategy_manager))
    refresh_button.pack(side=tk.RIGHT, padx=5)

    # Add a strategy dropdown for each row in a separate column
    def on_strategy_cell_click(event, strategies, df):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            row_id = tree.identify_row(event.y)
            if tree.heading(column, "text").lower() == "strategy":
                # Get the symbol, asset class, and position from the treeview item
                symbol = tree.set(row_id, 'symbol')
                asset_class = tree.set(row_id, 'Asset Class')
                position = float(tree.set(row_id, 'position'))

                # Find the corresponding dataframe row based on symbol, asset class, and position
                df_row = df[(df['symbol'] == symbol) & 
                            (df['asset class'] == asset_class) & 
                            (df['position'] == position)]
                
                # If no matching row found in the dataframe, set current_strategy to empty
                if df_row.empty:
                    current_strategy = ''
                else:
                    current_strategy = df_row['strategy'].iloc[0]

                # Position the combobox
                x, y, width, height = tree.bbox(row_id, column)
                pady = height // 2
                
                # Create the Combobox widget
                strategy_cb = ttk.Combobox(portfolio_tab, values=strategies)
                strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)
                strategy_cb.set(current_strategy)

                # Bind the selection event
                strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(tree, strategy_cb.get(), row_id))

    window.update_idletasks()  # Update the GUI to ensure treeview is drawn
    tree.bind("<Button-1>", lambda e: on_strategy_cell_click(e, strategies, df))
    tree.bind("<Button-3>", lambda e: on_right_click(e, tree, df,strategy_manager))  # <Button-3> is typically the right-click button

    scrollbar.config(command=tree.yview)

    def on_right_click(event, tree, df,strategy_manager):
        # Identify the row and column that was clicked
        region = tree.identify("region", event.x, event.y)

        if region == "cell":
            row_id = tree.identify_row(event.y)
            symbol = tree.set(row_id, 'symbol')
            asset_class = tree.set(row_id, 'Asset Class')
            position = float(tree.set(row_id, 'position'))

            menu = tk.Menu(window, tearoff=0)
            # Add a non-clickable menu entry as a title/header
            menu.add_command(label=f"{asset_class}: {position} {symbol}", state="disabled")
            menu.add_command(label="Delete Entry",command=lambda: delete_strategy(tree, row_id, df,strategy_manager))
            menu.add_command(label="Refresh View",command=lambda: refresh_portfolio_data(tree, strategy_manager))

            menu.post(event.x_root, event.y_root)

def populate_performance_tab(window,strategy_manager,performance_tab):
    pnl_lib = ac.get_library('pnl')
    pnl_df = pnl_lib.read(strategy_manager.ib_client.managedAccounts()[0]).data

    fig, ax = plt.subplots()
    pnl_df['total_equity'].plot(ax=ax)  # Plotting the total equity column
    ax.set_ylabel('Account Equity')
    
    # Embed the plot into the Tkinter window
    canvas = FigureCanvasTkAgg(fig, master=performance_tab)  
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    canvas.draw()

def open_portfolio_window(strategy_manager):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("900x450")

    # Create a Notebook widget & frames for each tab
    tab_control = ttk.Notebook(window)
    portfolio_tab = ttk.Frame(tab_control)
    performance_tab = ttk.Frame(tab_control)

    # Add tabs to the Notebook
    tab_control.add(portfolio_tab, text='Portfolio')
    tab_control.add(performance_tab, text='Performance')
    tab_control.pack(expand=1, fill="both")

    info_and_controls_frame = create_info_bar(strategy_manager,tab_control)

    populate_portfolio_tab(window,strategy_manager,portfolio_tab,info_and_controls_frame)
    populate_performance_tab(window,strategy_manager,performance_tab)

def delete_strategy(tree, row_id, df,strategy_manager):
    # Here you would handle the deletion of the strategy entry from the database
    symbol = tree.set(row_id, 'symbol')
    asset_class = tree.set(row_id, 'Asset Class')
    position = tree.set(row_id,'position')
    strategy = tree.set(row_id, 'strategy')

    strategy_manager.portfolio_manager.delete_symbol(symbol,asset_class,position,strategy)
    
    print(f"Entry marked as deleted: {symbol} {asset_class} position {position} , strategy {strategy}")

def get_portfolio_data(strategy_manager):
    df = strategy_manager.portfolio_manager.get_ib_positions_for_gui()
    data_list = df.to_dict('records')
    return data_list

def get_strategies(arctic_lib):
    # Fetch list of strategies from ArcticDB
    pass

def assign_strategy(item_id, strategy):
    print(f"from assign_strategy func: {item_id}")
    # Function to assign a strategy to a portfolio item and update in ArcticDB
    pass

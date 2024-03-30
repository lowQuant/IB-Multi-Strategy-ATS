import tkinter as tk
from tkinter import ttk
import pandas as pd
from datetime import datetime
from data_and_research import ac, fetch_strategies

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

def open_portfolio_window(strategy_manager):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("1000x600")

    # Top-level menu bar with "Performance" submenu
    menu_bar = tk.Menu(window)
    window.config(menu=menu_bar)

    # "Performance" submenu
    performance_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Performance", menu=performance_menu)
    performance_menu.add_command(label="Show PnL Graph", command=lambda: show_pnl_graph(strategy_manager, window))

    # Main frame for the Notebook (tab container)
    main_frame = tk.Frame(window)
    main_frame.pack(fill="both", expand=True)

    # Notebook (tabbed interface)
    tab_control = ttk.Notebook(main_frame)

    # Portfolio tab
    portfolio_tab = ttk.Frame(tab_control)
    tab_control.add(portfolio_tab, text='Portfolio')

    # Performance tab
    performance_tab = ttk.Frame(tab_control)
    tab_control.add(performance_tab, text='Performance')
    tab_control.pack(expand=1, fill="both")

    # Treeview for portfolio data
    columns = ("Symbol", "Asset Class", "Position", "FX", "Weight (%)", "Price", "Cost", "Pnl %", "Strategy")
    tree = ttk.Treeview(portfolio_tab, columns=columns, show='headings')
    for col, w in zip(columns, [50, 120, 60, 50, 60, 60, 60, 60, 100]):
        tree.column(col, stretch=tk.YES, minwidth=0, width=w)
        tree.heading(col, text=col.capitalize())
    tree.pack(side=tk.LEFT, fill="both", expand=True)

    # Scrollbar for treeview
    scrollbar = ttk.Scrollbar(portfolio_tab, orient="vertical", command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Fetch and display portfolio data in the treeview
    portfolio_data = get_portfolio_data(strategy_manager)  # This function should be defined elsewhere
    df = pd.DataFrame(portfolio_data)
    strategies,_ = fetch_strategies()  # Fetch list of strategies
    strategies.append("")  # This function should be defined elsewhere
    for item in portfolio_data:
        tree.insert("", tk.END, values=(
            item["symbol"], item["asset class"], item["position"],
            item["currency"], f"{item['% of nav']:.2f}", f"{item['marketPrice']:.2f}",
            f"{item['averageCost']:.2f}", f"{item['pnl %']:.2f}", item["strategy"]
        ))

    # Add account info at the bottom
    account_info_frame = tk.Frame(window)
    account_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
    tk.Label(account_info_frame, text=f"NAV: {total_equity:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f" Cash: {cash:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f" Margin: {margin:.2f}").pack(side=tk.LEFT)
    date_label = tk.Label(account_info_frame, text=f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    date_label.pack(side=tk.RIGHT, padx=5)

    # Refresh button
    refresh_button = tk.Button(account_info_frame, text="Refresh", command=lambda: refresh_portfolio_data(tree, strategy_manager))
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
                strategy_cb = ttk.Combobox(window, values=strategies)
                strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)
                strategy_cb.set(current_strategy)

                # Bind the selection event
                strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(tree, strategy_cb.get(), row_id))

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

    window.update_idletasks()  # Update the GUI to ensure treeview is drawn
    tree.bind("<Button-1>", lambda e: on_strategy_cell_click(e, strategies, df))
    tree.bind("<Button-3>", lambda e: on_right_click(e, tree, df,strategy_manager))  # <Button-3> is typically the right-click button
    tree.bind("<Button-2>", lambda e: on_right_click(e, tree, df,strategy_manager))

    scrollbar.config(command=tree.yview)

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

<script>
  import { onMount } from "svelte";
  import {
    fetchConversionKPI,
    fetchPOSTransactions,
    recordPOSTransaction,
    fetchProductInteractions,
  } from "../lib/api.js";

  let { skuCatalog = [] } = $props();

  let conversion = $state({
    total_footfall: 0,
    total_transactions: 0,
    conversion_rate: 0.0,
    total_revenue: 0.0,
    avg_basket_size: 0.0,
    product_pick_to_purchase_ratio: 0.0,
  });

  let transactions = $state([]);
  let interactions = $state([]);
  let isLoading = $state(false);

  // Cashier Register POS Input state
  let cart = $state([]);
  let selectedSkuId = $state("");
  let selectedQuantity = $state(1);
  let isCheckingOut = $state(false);
  let checkoutSuccessMsg = $state("");

  async function loadData() {
    isLoading = true;
    try {
      const [conv, txs, inters] = await Promise.all([
        fetchConversionKPI(),
        fetchPOSTransactions(),
        fetchProductInteractions(),
      ]);
      conversion = conv;
      transactions = txs || [];
      interactions = inters || [];
    } catch (e) {
      console.warn("Error loading POS/Conversion data", e);
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  });

  function addToCart() {
    if (!selectedSkuId) return;
    const sku = skuCatalog.find((s) => s.sku_id === selectedSkuId);
    const existing = cart.find((c) => c.sku_id === selectedSkuId);
    if (existing) {
      existing.quantity += selectedQuantity;
    } else {
      cart.push({
        sku_id: selectedSkuId,
        name: sku ? sku.name : selectedSkuId,
        quantity: selectedQuantity,
        price: 2.50, // default price if not in catalog
      });
    }
    selectedQuantity = 1;
  }

  function removeFromCart(index) {
    cart.splice(index, 1);
  }

  async function handleCheckout() {
    if (cart.length === 0) return;
    isCheckingOut = true;
    checkoutSuccessMsg = "";
    try {
      const txId = `tx_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      const total = cart.reduce((acc, item) => acc + item.price * item.quantity, 0);
      await recordPOSTransaction({
        transaction_id: txId,
        items: cart.map((i) => ({ sku_id: i.sku_id, quantity: i.quantity, price: i.price })),
        total_amount: total,
        payment_status: "completed",
      });
      checkoutSuccessMsg = `Transaction ${txId} recorded ($${total.toFixed(2)})`;
      cart = [];
      await loadData();
    } catch (e) {
      alert("Failed to submit transaction: " + e.message);
    } finally {
      isCheckingOut = false;
    }
  }
</script>

<div class="space-y-4">
  <!-- Top KPI Banner -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">Conversion Rate</span>
      <strong class="text-xl font-bold text-sky-800 font-mono">
        {(conversion.conversion_rate * 100).toFixed(1)}%
      </strong>
      <span class="text-[10px] font-mono text-slate-400">purchases / enters</span>
    </div>

    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">Total Revenue</span>
      <strong class="text-xl font-bold text-emerald-800 font-mono">
        ${conversion.total_revenue.toFixed(2)}
      </strong>
      <span class="text-[10px] font-mono text-slate-400">{conversion.total_transactions} sales</span>
    </div>

    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">Avg Basket Size</span>
      <strong class="text-xl font-bold text-slate-800 font-mono">
        {conversion.avg_basket_size.toFixed(1)} items
      </strong>
      <span class="text-[10px] font-mono text-slate-400">units per basket</span>
    </div>

    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">Pick-to-Purchase</span>
      <strong class="text-xl font-bold text-purple-800 font-mono">
        {(conversion.product_pick_to_purchase_ratio * 100).toFixed(1)}%
      </strong>
      <span class="text-[10px] font-mono text-slate-400">sales / interactions</span>
    </div>

    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">Store Footfall</span>
      <strong class="text-xl font-bold text-slate-800 font-mono">
        {conversion.total_footfall}
      </strong>
      <span class="text-[10px] font-mono text-slate-400">entry triggers</span>
    </div>

    <div class="bg-white border border-slate-200 rounded p-3 flex flex-col shadow-xs">
      <span class="text-[11px] font-mono text-slate-500 uppercase">POS Gateway</span>
      <strong class="text-xs font-semibold text-emerald-700 font-mono mt-1">
        LIVE REST API
      </strong>
      <span class="text-[10px] font-mono text-slate-400">Webhook Ready</span>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Interactive POS Cashier Register -->
    <div class="lg:col-span-1 bg-white border border-slate-200 rounded-lg p-4 shadow-xs flex flex-col justify-between">
      <div class="space-y-3">
        <div class="flex items-center justify-between border-b border-slate-100 pb-2">
          <h3 class="text-sm font-bold uppercase tracking-wider text-slate-900">Cashier Terminal Register</h3>
          <span class="px-2 py-0.5 text-[10px] font-mono bg-sky-50 text-sky-800 border border-sky-200 rounded">
            SIMULATE POS SCAN
          </span>
        </div>

        {#if checkoutSuccessMsg}
          <div class="p-2 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-mono rounded">
            ✓ {checkoutSuccessMsg}
          </div>
        {/if}

        <div class="flex items-center gap-2">
          <select
            bind:value={selectedSkuId}
            class="flex-1 bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            <option value="">-- Select SKU Product --</option>
            {#each skuCatalog as sku (sku.sku_id)}
              <option value={sku.sku_id}>{sku.name} ({sku.sku_id})</option>
            {/each}
          </select>

          <input
            type="number"
            min="1"
            max="20"
            bind:value={selectedQuantity}
            class="w-14 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-xs font-mono text-center focus:outline-none focus:ring-1 focus:ring-sky-500"
          />

          <button
            type="button"
            onclick={addToCart}
            disabled={!selectedSkuId}
            class="px-3 py-1.5 bg-slate-800 text-white rounded text-xs font-medium hover:bg-slate-700 cursor-pointer disabled:opacity-50"
          >
            + Scan
          </button>
        </div>

        <!-- Basket Items List -->
        <div class="min-h-[140px] max-h-[220px] overflow-y-auto border border-slate-100 rounded p-2 bg-slate-50/50 space-y-1.5">
          {#if cart.length === 0}
            <div class="h-28 flex items-center justify-center text-xs font-mono text-slate-400">
              Basket empty. Scan SKUs to check out.
            </div>
          {:else}
            {#each cart as item, idx}
              <div class="flex items-center justify-between text-xs font-mono bg-white p-1.5 border border-slate-200 rounded shadow-2xs">
                <div>
                  <strong class="text-slate-900 block truncate max-w-[140px]">{item.name}</strong>
                  <span class="text-slate-400 text-[10px]">{item.quantity} × ${item.price.toFixed(2)}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="font-bold text-slate-800">${(item.price * item.quantity).toFixed(2)}</span>
                  <button
                    type="button"
                    onclick={() => removeFromCart(idx)}
                    class="text-rose-500 hover:text-rose-700 text-xs px-1 cursor-pointer"
                  >
                    ✕
                  </button>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>

      <div class="pt-3 border-t border-slate-100 space-y-2">
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-500">Subtotal:</span>
          <strong class="text-base font-bold text-slate-900">
            ${cart.reduce((acc, i) => acc + i.price * i.quantity, 0).toFixed(2)}
          </strong>
        </div>
        <button
          type="button"
          onclick={handleCheckout}
          disabled={cart.length === 0 || isCheckingOut}
          class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium text-xs font-mono uppercase tracking-wider cursor-pointer shadow-xs disabled:opacity-50 transition-colors"
        >
          {isCheckingOut ? "Processing Transaction..." : "Complete POS Checkout"}
        </button>
      </div>
    </div>

    <!-- Right 2 Columns: Live Transactions & Product Interaction History -->
    <div class="lg:col-span-2 space-y-4">
      <!-- Recent Transactions -->
      <div class="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
        <div class="flex items-center justify-between pb-2 border-b border-slate-100 mb-2">
          <h3 class="text-sm font-bold uppercase tracking-wider text-slate-900">Recent POS Transactions</h3>
          <span class="text-xs font-mono text-slate-500">{transactions.length} records</span>
        </div>
        <div class="overflow-x-auto max-h-[200px] overflow-y-auto">
          {#if transactions.length === 0}
            <div class="py-8 text-center text-xs font-mono text-slate-400">
              No transactions recorded yet. Use the cashier register to process a sale.
            </div>
          {:else}
            <table class="w-full text-left text-xs font-mono">
              <thead class="bg-slate-50 text-slate-500 text-[10px] uppercase border-b border-slate-200">
                <tr>
                  <th class="py-1.5 px-2">Transaction ID</th>
                  <th class="py-1.5 px-2">Items</th>
                  <th class="py-1.5 px-2">Total</th>
                  <th class="py-1.5 px-2">Time</th>
                  <th class="py-1.5 px-2">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 text-slate-700">
                {#each transactions.slice(0, 10) as tx}
                  <tr>
                    <td class="py-1.5 px-2 font-semibold text-slate-900">{tx.transaction_id}</td>
                    <td class="py-1.5 px-2">{tx.item_count} items</td>
                    <td class="py-1.5 px-2 font-bold text-emerald-700">${Number(tx.total_amount || 0).toFixed(2)}</td>
                    <td class="py-1.5 px-2 text-slate-400">{new Date(tx.timestamp).toLocaleTimeString()}</td>
                    <td class="py-1.5 px-2">
                      <span class="px-1.5 py-0.2 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                        {tx.payment_status}
                      </span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </div>

      <!-- Shopper Product Interactions -->
      <div class="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
        <div class="flex items-center justify-between pb-2 border-b border-slate-100 mb-2">
          <h3 class="text-sm font-bold uppercase tracking-wider text-slate-900">Shopper Product Interactions</h3>
          <span class="text-xs font-mono text-slate-500">{interactions.length} interactions logged</span>
        </div>
        <div class="overflow-x-auto max-h-[200px] overflow-y-auto">
          {#if interactions.length === 0}
            <div class="py-8 text-center text-xs font-mono text-slate-400">
              No customer product interactions recorded yet. Customer dwell near shelves will appear here.
            </div>
          {:else}
            <table class="w-full text-left text-xs font-mono">
              <thead class="bg-slate-50 text-slate-500 text-[10px] uppercase border-b border-slate-200">
                <tr>
                  <th class="py-1.5 px-2">Track ID</th>
                  <th class="py-1.5 px-2">Zone</th>
                  <th class="py-1.5 px-2">Target SKU</th>
                  <th class="py-1.5 px-2">Dwell (sec)</th>
                  <th class="py-1.5 px-2">Timestamp</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 text-slate-700">
                {#each interactions.slice(0, 10) as inter}
                  <tr>
                    <td class="py-1.5 px-2 font-semibold">#{inter.track_id}</td>
                    <td class="py-1.5 px-2 text-slate-800">{inter.zone_id}</td>
                    <td class="py-1.5 px-2 font-medium text-sky-800">{inter.sku_id || "Unassigned"}</td>
                    <td class="py-1.5 px-2 font-bold">{inter.duration_sec.toFixed(1)}s</td>
                    <td class="py-1.5 px-2 text-slate-400">{new Date(inter.end_ts).toLocaleTimeString()}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

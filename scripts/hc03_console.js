/*
 * P0 / HC03: Run only on your LOCAL v0-goc demo with disposable data.
 * Log in, open /transactions/new-sale/, then paste into DevTools Console.
 * Replace <ITEM_ID> and <CUSTOMER_ID> with existing numeric IDs.
 * Prepare Item.price=100, Item.quantity=5 and a customer with last_name set.
 * The original app may accept this request: it CREATES a sale and consumes 2
 * units. Capture the response and /transactions/sales/ for BEFORE evidence.
 * Run the same script after HC03: expect HTTP 400 and no stock/sale changes.
 */
(async () => {
  const itemId = Number("<ITEM_ID>");
  const customerId = Number("<CUSTOMER_ID>");
  if (!Number.isSafeInteger(itemId) || itemId <= 0 ||
      !Number.isSafeInteger(customerId) || customerId <= 0) {
    throw new Error("Replace <ITEM_ID> and <CUSTOMER_ID> with positive IDs.");
  }
  if (!["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)) {
    throw new Error("Use the local demo only: this request can modify data.");
  }
  const cookie = document.cookie.split(";").map(value => value.trim())
    .find(value => value.startsWith("csrftoken="));
  const token = cookie ? decodeURIComponent(cookie.slice("csrftoken=".length))
    : document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
  if (!token) throw new Error("Missing CSRF token; open the sale form first.");
  const response = await fetch("/transactions/new-sale/", {
    method: "POST", credentials: "same-origin",
    headers: {"Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": token},
    body: JSON.stringify({customer: customerId,
      sub_total: 1, grand_total: 1, tax_percentage: 0, tax_amount: 0,
      amount_paid: 200, amount_change: 199,
      items: [{id: itemId, price: 0.01, quantity: 2, total_item: 1}]}),
  });
  console.log("HC03 BEFORE/AFTER HTTP", response.status);
  console.log(await response.text());
})();

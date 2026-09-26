# Order approval and enrollment

An order created after the release records the exact classes and offers purchased. The CMS shows that snapshot before an administrator approves payment. Approval grants access to those classes and changes the order status in one database transaction. A retry cannot grant twice. Rejection and expiration of a pending order grant nothing. Expiration of an approved order preserves access; any later revocation is a separate explicit operation.

Existing enrollments keep their current access. Orders present when the migration runs retain the manual fulfillment process. Historical package membership is reported as unknown where the checkout snapshot is absent. A package or class removed from the catalog remains stored so pending orders and existing access can still resolve it. Catalog removal archives the row; archiving a class also archives packages containing it.

An order grant records the order item, participant, class, package origin when applicable, class title, and purchased meeting count. The current `enrollments` table remains the effective access state; manually removing a class still removes that access. The grant ledger preserves the purchase origin for later participant/package reporting.

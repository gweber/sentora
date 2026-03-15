# Migration Strategy

Sentora uses MongoDB, which is schemaless. There is no formal migration tool (like Alembic for SQL databases). Instead, schema evolution is managed through idempotent index creation, backward-compatible field additions, and manual data transformation scripts when needed.

---

## Index Management

All indexes are defined in `backend/db_indexes.py` and applied on every application startup via `ensure_all_indexes(db)`.

- **Idempotent**: MongoDB's `create_index` is a no-op if the index already exists with the same specification.
- **Background**: All indexes are created with `background=True` to avoid blocking reads/writes during creation.
- **Adding a new index**: Add the `create_index` call to `db_indexes.py`. It will be created on the next restart.
- **Removing an index**: Remove the `create_index` call from `db_indexes.py`, then manually drop the index in production:
  ```javascript
  // In mongosh
  use sentora
  db.collection_name.dropIndex("index_name")
  ```

---

## Adding New Fields

MongoDB documents are flexible -- new fields can be added without migrating existing documents.

### Strategy: Lazy defaults

1. Add the field to the Pydantic entity model with a default value:
   ```python
   class Agent(BaseModel):
       new_field: str = ""  # default for existing docs
   ```

2. New documents will include the field. Existing documents will use the Pydantic default when loaded.

3. If the field needs to be queryable, add an index in `db_indexes.py`.

### Strategy: Backfill

If existing documents must be updated (e.g., for aggregation queries that need the field to exist):

```python
# One-time backfill script
from database import get_db

async def backfill_new_field():
    db = get_db()
    result = await db["collection"].update_many(
        {"new_field": {"$exists": False}},
        {"$set": {"new_field": "default_value"}},
    )
    print(f"Updated {result.modified_count} documents")
```

Run via a management command or directly in `mongosh`:
```javascript
db.collection.updateMany(
  { new_field: { $exists: false } },
  { $set: { new_field: "default_value" } }
)
```

---

## Renaming Fields

Field renames require a two-phase approach to avoid downtime:

### Phase 1: Write both fields (backward-compatible)
1. Update the application code to write both the old and new field names.
2. Deploy this version.

### Phase 2: Migrate data and drop old field
1. Rename the field in existing documents:
   ```javascript
   db.collection.updateMany(
     { old_field: { $exists: true } },
     { $rename: { "old_field": "new_field" } }
   )
   ```
2. Update the application code to read/write only the new field.
3. Deploy the final version.
4. Drop any index on the old field name; create one for the new field if needed.

---

## Removing Fields

Fields can be removed without breaking existing documents:

1. Remove the field from the Pydantic model.
2. Optionally clean up stored data:
   ```javascript
   db.collection.updateMany({}, { $unset: { "removed_field": "" } })
   ```
3. Remove any associated indexes.

---

## Collection-Level Changes

### Adding a new collection
1. Create the entity model, repository, and service.
2. Add indexes to `db_indexes.py`.
3. MongoDB creates the collection automatically on first write.

### Dropping a collection
1. Remove all application code that references it.
2. Drop in production:
   ```javascript
   db.collection_to_drop.drop()
   ```

---

## Version Upgrade Checklist

Follow this checklist when deploying a new version of Sentora:

### Pre-deployment
- [ ] Review the CHANGELOG for breaking changes or required migrations.
- [ ] Back up the MongoDB database:
  ```bash
  mongodump --db sentora --out /backup/$(date +%Y%m%d)
  ```
- [ ] If the release notes mention data transformations, prepare and test the migration script against a copy of production data.

### Deployment
- [ ] Pull the new version and build:
  ```bash
  git pull origin main
  cd frontend && npm install && npm run build
  cd ../backend && pip install -r requirements.txt
  ```
  Or rebuild Docker images:
  ```bash
  docker compose build
  ```
- [ ] Run any required data migration scripts **before** starting the new version (if specified in release notes).
- [ ] Start the new version. Index changes in `db_indexes.py` apply automatically on startup.
- [ ] Verify the health endpoint: `curl http://localhost:5002/api/v1/health`

### Post-deployment
- [ ] Confirm all pages load correctly in the frontend.
- [ ] Check the Audit Log for any startup errors.
- [ ] Run a test sync (incremental) to verify S1 connectivity.
- [ ] If taxonomy seed data was updated, the seed will auto-apply only if `taxonomy_categories` is empty. For updates to existing seed data, manual intervention may be needed.

---

## Rollback Strategy

### Quick rollback (code only)
If the new version has bugs but no data migration was performed:
1. Stop the new version.
2. Deploy the previous version:
   ```bash
   git checkout <previous-tag>
   # Rebuild and restart
   ```
3. The old version will work with the existing data since no schema changes were made.

### Rollback after data migration
If a data migration was applied and must be reverted:
1. Stop the application.
2. Restore from the pre-deployment backup:
   ```bash
   mongorestore --db sentora --drop /backup/YYYYMMDD/sentora/
   ```
3. Deploy the previous version.

### Rollback with forward-compatible changes
If the migration only added new fields (with defaults), the old version will simply ignore them. No data restore is needed -- just deploy the old code.

---

## Data Integrity Notes

- **Singleton documents** (`app_config`, `s1_sync_meta`, `s1_sync_checkpoint`): These use fixed `_id` values and are upserted. They will be recreated automatically if deleted.
- **Materialized views** (`app_summaries`): Rebuilt automatically after syncs and taxonomy changes. Can be manually rebuilt from the Apps page or Sync page.
- **Taxonomy seed data**: Only inserted when `taxonomy_categories` is empty. Modifying seed YAML does not update existing entries -- use the Taxonomy UI for changes.
- **TTL index on audit_log**: Entries older than 90 days are automatically deleted by MongoDB. This is not configurable without modifying `db_indexes.py`.

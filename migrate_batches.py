import asyncio
from app.db.db import engine
from sqlalchemy import text

async def run_migration():
    print("Starting migration...")
    async with engine.begin() as conn:
        # Create batches table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS batches (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
            );
        """))
        
        # We need at least one batch to assign existing data to
        res = await conn.execute(text("SELECT id FROM batches LIMIT 1"))
        batch = res.fetchone()
        
        if not batch:
            await conn.execute(text("INSERT INTO batches (name, is_active) VALUES ('Batch 1 (Legacy)', true)"))
            res = await conn.execute(text("SELECT id FROM batches LIMIT 1"))
            batch = res.fetchone()
            
        batch_id = batch[0]
        
        # Add batch_id to classes if not exists
        await conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='classes' AND column_name='batch_id') THEN 
                    ALTER TABLE classes ADD COLUMN batch_id UUID REFERENCES batches(id); 
                END IF; 
            END $$;
        """))
        
        # Update existing classes to use the legacy batch
        await conn.execute(text(f"UPDATE classes SET batch_id = '{batch_id}' WHERE batch_id IS NULL"))
        
        # Add batch_id to packages if not exists
        await conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='packages' AND column_name='batch_id') THEN 
                    ALTER TABLE packages ADD COLUMN batch_id UUID REFERENCES batches(id); 
                END IF; 
            END $$;
        """))
        
        # Update existing packages to use the legacy batch
        await conn.execute(text(f"UPDATE packages SET batch_id = '{batch_id}' WHERE batch_id IS NULL"))

        print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(run_migration())

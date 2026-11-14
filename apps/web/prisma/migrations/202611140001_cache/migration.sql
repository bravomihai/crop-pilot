CREATE TABLE "DataCache" (
 "key" TEXT NOT NULL,
 "namespace" TEXT NOT NULL,
 "payload" JSONB NOT NULL,
 "expiresAt" TIMESTAMP(3) NOT NULL,
 "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "DataCache_pkey" PRIMARY KEY ("key")
);
CREATE INDEX "DataCache_expiresAt_idx" ON "DataCache"("expiresAt");

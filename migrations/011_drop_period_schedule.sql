-- Remove period_schedule table. Curriculum data now lives in the normalized
-- week / lesson / concept / skill / concept_skill tables.

drop policy if exists "period_schedule: owner select" on period_schedule;
drop policy if exists "period_schedule: owner insert" on period_schedule;
drop policy if exists "period_schedule: owner update" on period_schedule;

drop table if exists period_schedule;

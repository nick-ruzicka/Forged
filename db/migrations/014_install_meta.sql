ALTER TABLE tools ADD COLUMN IF NOT EXISTS install_meta TEXT;
-- JSON: {"type":"brew","formula":"raycast","cask":true}
-- or:   {"type":"pip","package":"autoagent"}
-- or:   {"type":"dmg","url":"https://...","filename":"app.dmg"}

# Player schema 10 before Antimagic removal

Exact schema and identity preceding player schema 11. These files are offline
recording evidence. Current live peers require schema 11. Native RecordedSequence
schema 2 and public PlayerSequence schema 5 are separate contracts.

The native passive reader accepts empty retired suppression metadata in ordinary
old records. Recordings with active Antimagic suppression are explicitly unsupported;
keep their original bytes and this old contract rather than discarding those facts.

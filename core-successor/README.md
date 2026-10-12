# Core successor 0.4.0-a01.1 (POS-A01)

Copy-on-write successor of sealed Core 0.3.1-rc.1 (40ffdac4…27e3).

- Pair tables and existing inventory commands remain.
- Additive 
03 schema: ssets, sset_identifiers, optional sset_events.asset_id.
- New commands: 
egister_asset, dd_asset_identifier.
- New queries: get_asset, list_assets (plus ind_asset via asset identifiers).

Do not edit sealed archives under rozen/.

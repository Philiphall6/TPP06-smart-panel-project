# Password candidates to try

These values were shared as **candidates** for local TPP06 login. On the panel documented here, the recovered password matched one of the candidates published in the Home Assistant forum. They still need to be tested on each panel: they do not come from a dump published in this repository.

Try them only on a panel that you are authorised to access, **before desoldering the NAND or using the XGecu**:

```text
6b7835db
80a69d0f
de8ba884
33a644d0
314b6d93
5bfd1d91
```

If none works, do not keep retrying: return to the UART logs and local system analysis. Reading the NAND with the XGecu then becomes the next step to create a backup and understand the system. Do not publish a NAND dump, hash, or device-specific credential.

Community source: [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6).

# Field report: NAND read and password-hash search

> This report covers two MOES / Tuya TPP06 panels equipped with a GigaDevice NAND device. It records one successful maintenance path; it is not a guarantee that every panel has the same layout or credentials.

## Reading the NAND

Reading the NAND in-circuit with pogo pins did not work in this case. The chip was therefore removed with hot air, read with an XGecu T48 and a suitable adapter, then soldered back onto the board.

Allow the board to heat evenly before lifting the chip. A hot-air station setting of **350 °C** was used for these two panels. The appropriate temperature and airflow depend on the station, nozzle and board; avoid levering the package.

## Password-hash search

When extracting the SquashFS partitions, an MD5crypt hash beginning with `$1$` was found. This appears to be unrelated to the intended root-password recovery method.

For these two panels, the relevant DEScrypt hash was found by searching the **raw XGPro NAND dump** directly for `root:` or `root`, without extracting the partitions first.

Do not publish the raw dump, the hash, the resulting password, device identifiers or keys. Keep them in protected local storage.

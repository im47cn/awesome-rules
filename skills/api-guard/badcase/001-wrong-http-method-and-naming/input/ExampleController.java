@RestController
@RequestMapping("/waybill")
public class WaybillController {

    @GetMapping("/syncWaybill/{id}")
    public Result syncWaybill(@PathVariable String id) {
        return Result.success();
    }

    @PostMapping("/list")
    public Result list(@RequestBody QueryDTO dto) {
        return Result.success();
    }
}

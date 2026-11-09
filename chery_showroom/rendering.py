"""One camera/export interface for classic MuJoCo and its installed Filament backend."""
import numpy as np
import mujoco

class FilamentRenderer:
    def __init__(self,model,height,width):
        # Resource registration is provided by the installed MuJoCo wheel.
        from mujoco.experimental.studio import window  # noqa: F401
        import mujoco._render_filament as f
        from mujoco.rendering.filament import renderer
        self.model=model;self.f=f;self._camera=None;self._settle=1
        self.ctx=f.Context(f.ContextConfig(graphics_api=f.GraphicsApi.GRAPHICS_API_VULKAN))
        self.renderer=renderer.Renderer(self.ctx);self.objects=f.ModelObjects(self.ctx,model)
        self.scene=self.renderer.scene('showroom');self.scene.configure_from_model(model)
        self.lights=f.ModelLights(self.scene,self.objects);self.drawables=f.ModelRenderables(self.scene,self.objects)
        self.buffer=np.empty((height,width,3),dtype=np.uint8);self.renderer.target('output',self.buffer)
        self.renderer.view('camera',scene='showroom',target='output')
    def update_scene(self,data,camera,scene_option=None):
        if camera!=self._camera:self._settle=8;self._camera=camera
        opt=scene_option or options(camera)
        self.drawables.set_options(opt);self.drawables.update(data);self.lights.update(data)
        vcam=mujoco.MjvCamera();vcam.type=mujoco.mjtCamera.mjCAMERA_FIXED
        vcam.fixedcamid=self.model.camera(camera).id if isinstance(camera,str) else camera
        self.renderer.update_camera('camera',mujoco.mjv_camera2GLCamera(self.model,data,vcam))
    def render(self):
        for _ in range(self._settle):self.renderer.render()
        self._settle=1
        return self.buffer.copy()
    def close(self):
        # The Python wrappers own native resources; release them in dependency order.
        self.drawables=None;self.lights=None;self.scene=None;self.objects=None;self.renderer=None;self.ctx=None

def options(camera):
    opt=mujoco.MjvOption();opt.geomgroup[5]=False
    opt.geomgroup[4]=camera not in ('overview','showroom_overview')
    opt.sitegroup[5]=False
    return opt

def create_renderer(model,height,width,backend='classic'):
    if backend=='classic':return mujoco.Renderer(model,height=height,width=width)
    if backend=='filament':return FilamentRenderer(model,height,width)
    raise ValueError('Unknown renderer: '+backend)

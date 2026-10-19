#include <onnxruntime_cxx_api.h>
#include <iostream>
#include <vector>
int main(int argc,char**argv){
 Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"test"); Ort::SessionOptions opts; opts.SetIntraOpNumThreads(1);
 Ort::Session sess(env,argv[1],opts); Ort::AllocatorWithDefaultOptions alloc;
 auto in=sess.GetInputNameAllocated(0,alloc),out=sess.GetOutputNameAllocated(0,alloc);
 auto shape=sess.GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();shape[0]=1;
 size_t n=1;for(auto v:shape)n*=v;std::cerr<<"input="<<n<<"\n";
 std::vector<float>x(n);auto mem=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
 while(std::cin>>x[0]){for(size_t i=1;i<n;i++)std::cin>>x[i];
 auto t=Ort::Value::CreateTensor<float>(mem,x.data(),n,shape.data(),shape.size());
 const char* ins[]={in.get()};const char* outs[]={out.get()};auto r=sess.Run(Ort::RunOptions{nullptr},ins,&t,1,outs,1);
 auto count=r[0].GetTensorTypeAndShapeInfo().GetElementCount();auto p=r[0].GetTensorData<float>();
 for(size_t i=0;i<count;i++)std::cout<<p[i]<<' ';std::cout<<std::endl;
 }
}
